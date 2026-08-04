"""
Scheduler - NYSE seans saatine bagli iki kademeli dongu (plan bolum 5).

Faz 1 kapsami:
  - 15:45 TR (~acilis-45dk ET) hazirlik: evren scrape + likidite filtresi,
    bilanco takvimi yenileme, rejim tespiti, hazirlik ozeti
  - Seans ici (16:30-23:00 TR): 15 dk'da bir KABA TARAMA - tum filtrelenmis
    evren, yfinance 1D+1h; SIGNAL dogrudan Telegram'a (ince tarama Phase 2)
  - 23:15 TR (~kapanis+15dk ET) gun sonu ozeti
  - Hafta sonu / tatilde uyur; per-symbol hata izolasyonu
Zamanlar ET uzerinden hesaplanir; TR karsiliklari DST'den bagimsiz korunur.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import date, datetime, timedelta, timezone

from app.config.settings import Settings
from app.formatting import telegram_formatter
from app.integrations.telegram_notifier import TelegramNotifier
from app.logging_setup import kv
from app.models.decision import Decision, DecisionType, MarketRegime, SetupType
from app.services.earnings_service import EarningsService
from app.services.market_calendar import MarketCalendar
from app.services import market_report, premarket_watch
from app.services.market_data_service import MarketDataService
from app.services.state_store import StateStore
from app.services.universe import UniverseProvider
from app.strategies import signal_engine
from app.strategies.regime_detector import RegimeResult, classify_market_regime
from app.strategies.session_guard import (
    BLOCKED_KILL_SWITCH, BLOCKED_OPEN_BLACKOUT, BLOCKED_PORTFOLIO,
    in_open_blackout, index_kill_switch)

log = logging.getLogger("scheduler")

_BENCH = "SPY"


def _json_or_none(raw):
    """SMC etiketleri DB'de JSON metin olarak durur; panoya nesne verilir.
    Bozuk/eksik kayitta None (eski satirlar - uydurma etiket uretilmez)."""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


class Scheduler:
    def __init__(self, settings: Settings, market_data: MarketDataService,
                 universe: UniverseProvider, earnings: EarningsService,
                 calendar: MarketCalendar, store: StateStore,
                 notifier: TelegramNotifier, tracker=None,
                 gist_backup=None, commentary=None, news=None) -> None:
        self._settings = settings
        self._md = market_data
        self._universe = universe
        self._earnings = earnings
        self._calendar = calendar
        self._store = store
        self._notifier = notifier
        self._tracker = tracker      # None -> golge takip kapali
        self._gist = gist_backup     # None -> gist yedekleme kapali
        self._commentary = commentary  # None -> otomatik degerlendirme kapali
        self._news = news              # None -> haber akisi kapali
        self._exit_lab = None          # main.py kurulumda baglar (v3.19)
        # v3.21: KATMAN 2 - bagimsiz aday GIRIS stratejileri (ayni cikis)
        from app.services.strategy_lab import StrategyLab
        self._strategy_lab = StrategyLab(settings=settings)
        self._params = settings.strategy_params

        self._last_coarse = 0.0
        self._last_fine = 0.0
        self._zone_notified: set = set()      # sinyal basina tek "bolgede" bildirimi
        self._reeval_at: dict = {}            # sembol -> son tekrar-degerlendirme ts
        self.last_fine_info: dict = {}
        self._last_heartbeat = 0.0
        self._deadman_date = None
        self.data_comparison = None      # Asama 0: paralel veri gozlemi
        self._datacmp_date = None
        self.wallet: dict = {}
        self.wallet_rows: list = []
        self._weekly_date = None
        self._daily_cache: dict = {}
        self._daily_cache_date: date | None = None
        self._prep_date: date | None = None
        self._eod_date: date | None = None
        self._gap_watch_date: date | None = None
        self._regime = RegimeResult(regime=MarketRegime.UNKNOWN, detail="not computed")
        self._watchlist: list[dict] = []
        self._signals_today: list[str] = []
        self.last_scan_info: dict = {}
        self.last_prep_info: dict = {}
        self.last_market_note: str = ""
        self.last_gap_watch: dict = {}
        self.progress: str = ""

    # ------------------------------------------------------------- disari API
    @property
    def regime(self) -> RegimeResult:
        return self._regime

    @property
    def watchlist(self) -> list[dict]:
        return list(self._watchlist)

    def start_background(self) -> None:
        thread = threading.Thread(target=self._loop, daemon=True, name="scan-loop")
        thread.start()

    # ---------------------------------------------------------------- ana dongu
    def _loop(self) -> None:
        s = self._settings
        log.info(kv(event="scheduler_start", coarse_interval_s=s.COARSE_SCAN_INTERVAL_SEC,
                    htf=s.HTF, mtf=s.MTF))
        self._startup_message()
        while True:
            try:
                self.tick()
            except Exception:
                log.exception(kv(event="loop_error"))
            time.sleep(s.LOOP_TICK_SEC)

    def tick(self, now_et: datetime | None = None) -> None:
        """Tek zamanlayici adimi - test edilebilirlik icin now enjekte edilebilir."""
        now_et = now_et or self._calendar.now_et()
        today = now_et.date()
        # v3.12: HABER YENILEME TICK'IN SONUNA ALINDI (asagi bak).
        # Eskiden burada, tick'in BASINDA senkron kosuyordu; 3 Agu'da
        # Finnhub /company-news timeout'a dustu ve her turda 5 x 15 sn
        # = 75 sn boyunca tick'i kilitledi - gap nobetinin ve seans ici
        # taramalarin ONUNDE. Sira kurali: once islem-kritik is
        # (gap nobeti -> hazirlik -> taramalar), en sonda kozmetik veri.
        if self._gist is not None and \
                time.time() - self._last_heartbeat >= self._settings.HEARTBEAT_SEC:
            self._last_heartbeat = time.time()
            try:
                self._gist.heartbeat(self.build_heartbeat())
            except Exception:
                log.exception(kv(event="heartbeat_error"))
        session = self._calendar.session_times(today)
        if session is None:
            return  # hafta sonu / tatil: uyu
        open_dt, close_dt = session
        prep_dt = open_dt - timedelta(minutes=self._settings.PREP_LEAD_MIN)
        eod_dt = close_dt + timedelta(minutes=self._settings.EOD_DELAY_MIN)

        watch_dt = open_dt - timedelta(minutes=self._settings.PREMARKET_LEAD_MIN)
        self._maybe_weekly(now_et)
        self._maybe_compare_data(today)
        # Not (30 Tem): hazirlik sarti kaldirildi - restart sonrasi nobet
        # gecikmesin. Nobetin girdisi gist'ten donen pozisyonlar + quote;
        # izleme listesi adaylari o an bos olabilir, kritik olan pozisyonlar.
        if (self._settings.PREMARKET_WATCH
                and watch_dt <= now_et < open_dt
                and self._gap_watch_date != today):
            self.run_gap_watch(today)
        if now_et >= prep_dt and self._prep_date != today:
            self.run_prep(today)
        if open_dt <= now_et < close_dt:
            self._deadman_check(now_et, open_dt, today)
            if time.time() - self._last_coarse >= self._settings.COARSE_SCAN_INTERVAL_SEC:
                self.run_coarse_scan(send_telegram=True)
                self._last_coarse = time.time()
            if time.time() - self._last_fine >= self._settings.FINE_SCAN_INTERVAL_SEC:
                try:
                    self.run_fine_scan()      # ince tarama kaba taramayi ASLA dusurmez
                except Exception:
                    log.exception(kv(event="fine_scan_error"))
                self._last_fine = time.time()
        if now_et >= eod_dt and self._eod_date != today and self._prep_date == today:
            self.run_eod(today)
        # aday strateji laboratuvari: gunde bir kez, ARKA PLANDA baslar
        # (kendi kilidi var; hazirligi beklemeden gorunur olsun diye
        # tick'ten de tetiklenir - tick bloklanmaz).
        self._kick_strategy_lab()
        # --- en son: kozmetik veri (haber akisi) ---
        if self._news is not None:
            try:
                self._news.maybe_refresh(self._news_symbols(), today)
            except Exception:
                log.exception(kv(event="news_refresh_error"))

    # ------------------------------------------------------- 15:45 TR hazirlik
    def run_prep(self, today: date) -> None:
        log.info(kv(event="prep_start", date=today.isoformat()))
        self._prep_date = today
        self._signals_today = []
        self.progress = "hazirlik: evren cekiliyor + likidite filtresi"
        symbols = self._universe.refresh(force=True)
        # v3.11: evren tazelenemediyse SESSIZ KALMA. 31 Tem'de likidite
        # filtresi bos dondu, liste 30 Tem'de kaldi ve 3 gun boyunca
        # hicbir alarm calmadi - bayat evrenle taramak, yeni likit
        # sembolleri kacirmak ve delist olmuslari taramak demektir.
        try:
            stale = self._universe.stale_days()
            if stale is None or stale > 0:
                log.warning(kv(event="universe_stale", stale_days=stale,
                               count=len(symbols)))
                self._notifier.send(
                    f"UYARI: evren listesi tazelenemedi "
                    f"(bayatlik: {stale if stale is not None else '?'} gun, "
                    f"{len(symbols)} sembol). Tarama eski listeyle suruyor.")
        except Exception:
            log.exception(kv(event="universe_stale_check_failed"))
        self.progress = f"hazirlik: bilanco takvimi ({len(symbols)} sembol)"
        self._kick_strategy_lab()
        self._earnings.refresh(today, force=True)
        # v3.16: takvim yuklenemediyse SESSIZ KALMA - bu bir KARAR
        # filtresidir; yoksa motor fail-closed'a gecer ve o gun sinyal
        # uretilmez, kullanici sebebini bilmelidir.
        try:
            est = self._earnings.status()
            if not est.get("ready"):
                log.error(kv(event="earnings_unavailable", **est))
                self._notifier.send(
                    "UYARI: bilanco takvimi yuklenemedi (Finnhub). Guvenli "
                    "taraf devrede: takvim gelene kadar YENI SINYAL "
                    "URETILMEYECEK. 10 dk'da bir yeniden denenecek.")
        except Exception:
            log.exception(kv(event="earnings_status_check_failed"))
        self.progress = f"hazirlik: gunluk veri isitiliyor ({len(symbols)} sembol)"

        # Gunluk cache'i simdiden isit: rejim + piyasa notu buradan cikar,
        # seans acilisindaki ilk kaba tarama da hazir veriyle baslar.
        fetch_list = symbols + [s for s in self._settings.regime_symbols
                                if s not in symbols]
        if _BENCH not in fetch_list:
            fetch_list.append(_BENCH)
        daily = self._get_daily_cached(fetch_list, today)
        idx = self._settings.regime_symbols
        spy_df = daily.get(idx[0]).to_dataframe() if idx and idx[0] in daily else None
        qqq_df = (daily.get(idx[1]).to_dataframe()
                  if len(idx) > 1 and idx[1] in daily else None)
        self._regime = classify_market_regime(spy_df, qqq_df)

        try:
            blackout = sum(
                1 for s in symbols
                if (info := self._earnings.info(s, today)).days_to is not None
                and abs(info.days_to) <= self._params.earnings_blackout_days)
            snap = market_report.build_market_snapshot(
                daily, symbols, self._regime.regime.value,
                earnings_blackout_count=blackout)
            self.last_market_note = market_report.render_market_note(snap)
        except Exception:
            log.exception(kv(event="market_note_error"))
            self.last_market_note = ""
        self.last_prep_info = {"date": today.isoformat(),
                               "universe": len(symbols),
                               "regime": self._regime.regime.value}
        self.progress = ""
        log.info(kv(event="prep_done", universe=len(symbols),
                    regime=self._regime.regime.value))
        if self._settings.SEND_PREP_SUMMARY:
            note = f"\n\n{self.last_market_note}" if self.last_market_note else ""
            self._send(
                f"Hazirlik tamam ({today.isoformat()})\n"
                f"Evren: {len(symbols)} sembol (likidite filtreli)\n"
                f"Rejim: {self._regime.regime.value} ({self._regime.detail})\n"
                f"Kaba tarama seans acilisiyla baslar "
                f"({self._settings.COARSE_SCAN_INTERVAL_SEC // 60} dk aralik)."
                f"{note}"
            )

    def _compute_regime(self) -> RegimeResult:
        idx = self._settings.regime_symbols
        daily = self._md.get_daily_bulk(idx)
        spy = daily.get(idx[0]).to_dataframe() if idx and idx[0] in daily else None
        qqq = (daily.get(idx[1]).to_dataframe()
               if len(idx) > 1 and idx[1] in daily else None)
        return classify_market_regime(spy, qqq)

    # -------------------------------------------------------------- kaba tarama
    def _get_daily_cached(self, fetch_list: list[str], today: date) -> dict:
        """Gunluk mumlar seans icinde degismez -> gunde BIR kez indirilir.
        Yahoo rate limitine karsi en buyuk tasarruf noktalarindan biri."""
        if self._daily_cache_date != today:
            self._daily_cache = {}
            self._daily_cache_date = today
        missing = [s for s in fetch_list if s not in self._daily_cache]
        if missing:
            self._daily_cache.update(self._md.get_daily_bulk(missing))
        return self._daily_cache

    def run_coarse_scan(self, send_telegram: bool = True) -> list[Decision]:
        """Iki gecisli kaba tarama (Yahoo rate limitine gore tasarlandi):
        1. gecis: SADECE gunluk veri (gunde 1 kez indirilir/cache) ile
           rejim + trend + bilanco filtreleri -> aday listesi
        2. gecis: 1h veri YALNIZ adaylar icin indirilir (<= HOURLY_FETCH_MAX)
           -> setup/hacim/RR filtreleri -> SIGNAL"""
        scan_t0 = time.time()
        today = self._calendar.now_et().date()
        symbols = self._universe.get_symbols()
        if not symbols:
            log.warning(kv(event="coarse_scan_empty_universe"))
            return []
        self._earnings.refresh(today)

        fetch_list = symbols + [s for s in self._settings.regime_symbols
                                if s not in symbols]
        if _BENCH not in fetch_list:
            fetch_list.append(_BENCH)
        self.progress = f"tarama: gunluk veri ({len(fetch_list)} sembol)"
        daily = self._get_daily_cached(fetch_list, today)

        idx = self._settings.regime_symbols
        spy_df = daily.get(idx[0]).to_dataframe() if idx and idx[0] in daily else None
        qqq_df = (daily.get(idx[1]).to_dataframe()
                  if len(idx) > 1 and idx[1] in daily else None)
        self._regime = classify_market_regime(spy_df, qqq_df)
        bench_df = daily.get(_BENCH).to_dataframe() if _BENCH in daily else None

        self.progress = "tarama: 1. gecis (gunluk filtreler)"
        # --- 1. gecis: gunluk filtreler (1h verisi olmadan) ---
        pass1: dict[str, Decision] = {}
        candidates: list[str] = []
        for symbol in symbols:
            try:
                # pass-1 SIGNAL uretemez (1h yok) -> takvim yokken
                # eleme yapma, yoksa hicbir aday pass-2'ye ulasmaz
                # ve yedek kaynak hic calismaz (kilitlenme).
                e_info = self._earnings.info(symbol, today, strict=False)
                d = signal_engine.evaluate(symbol, daily.get(symbol), None,
                                           self._regime, self._params,
                                           bench_df, e_info)
            except Exception:
                log.exception(kv(event="scan_error", symbol=symbol, stage=1))
                continue
            pass1[symbol] = d
            if d.data_missing == ["hourly_klines"]:
                candidates.append(symbol)
        capped = candidates[: self._settings.HOURLY_FETCH_MAX]
        if len(candidates) > len(capped):
            log.warning(kv(event="hourly_fetch_capped",
                           candidates=len(candidates), cap=len(capped)))

        # --- 2. gecis: adaylar icin 1h veri + tam pipeline ---
        self.progress = f"tarama: 1h verisi indiriliyor ({len(capped)} aday)"
        hourly = self._md.get_hourly_bulk(capped) if capped else {}
        self.progress = "tarama: 2. gecis (setup/hacim/RR)"
        # v3.19: 12-1 KESITSEL MOMENTUM yuzdeligi (yalniz ETIKET - karara
        # karismaz). Backtest bulgusu: tek kararli pozitif giris ailesi
        # (NW t=3.3, iki alt donemde ayni yonde). Sinyal dogarken evren
        # icindeki yuzdeligi damgalanir; kohort dolunca "ust dilim
        # sinyalleri daha mi iyi" sorusu KENDI defterimizden cevaplanir.
        mom_pct_map = self._momentum_pcts(daily)
        atr_pct_map = self._atr_pcts(daily)
        # v3.18: Finnhub takvimi yoksa YALNIZ bu adaylar icin yedek
        # kaynak (yfinance) calisir - 300 sembol degil ~50.
        try:
            self._earnings.prefetch(list(hourly.keys()), today)
        except Exception:
            log.exception(kv(event="earnings_prefetch_failed"))
        results: list[Decision] = []
        watch: list[dict] = []
        blocked_count = 0
        for symbol, d in pass1.items():
            try:
                if symbol in hourly:
                    e_info = self._earnings.info(symbol, today)
                    d = signal_engine.evaluate(symbol, daily.get(symbol),
                                               hourly[symbol].closed_only(),
                                               self._regime,
                                               self._params, bench_df, e_info)
                if d.decision is DecisionType.SIGNAL:
                    d.time_stop_date = self._calendar.add_trading_days(
                        today, self._params.time_stop_days).isoformat()
                    d.session_phase = self._calendar.session_phase()
            except Exception:
                log.exception(kv(event="scan_error", symbol=symbol, stage=2))
                continue
            results.append(d)
            # v3.9: giris karari TEK noktada ve maybe_track'ten ONCE.
            # Eski akista yon/kume tavani maybe_track'ten SONRA kontrol
            # ediliyordu -> ayni sinyal hem blocked=0 (karneye sizar) hem
            # blocked=2 olarak CIFT kaydedilebiliyor, ustelik tavan sayimi
            # sinyalin kendi satirini da sayiyordu. Duzeltildi (2 Agu).
            block = (self._entry_block(d)
                     if d.decision is DecisionType.SIGNAL else None)
            if self._tracker is not None:
                try:
                    if symbol in hourly:
                        self._tracker.record_candles(hourly[symbol])
                    if symbol in daily:
                        self._tracker.record_candles(daily[symbol])
                    self._tracker.record_decision(d)
                    if symbol in hourly:
                        if block is None:
                            _ap = atr_pct_map.get(symbol) or (None, None)
                            self._tracker.maybe_track(
                                d, hourly[symbol],
                                mom_pct=mom_pct_map.get(symbol),
                                atr_pct=_ap[0], atr_rank=_ap[1])
                        else:
                            self._tracker.track_blocked(
                                d, hourly[symbol], block[0], block[1])
                    self._tracker.evaluate_open(symbol)
                except Exception:
                    log.exception(kv(event="tracker_error", symbol=symbol))
            self._store.save_result(symbol, d.contract_dict())
            self._collect_watch(d, watch, hourly.get(symbol))
            if block is not None:
                blocked_count += 1
                log.info(kv(event="entry_blocked", symbol=symbol,
                            blocked_class=block[1], reason=block[0]))
            elif send_telegram:
                self._dispatch(d)
            log.info(kv(event="scan", symbol=symbol, decision=d.decision.value,
                        direction=d.direction.value,
                        reason=d.reject_reason or d.setup_type.value))

        if self._tracker is not None:
            self._evaluate_orphans(set(pass1.keys()))
        self._watchlist = watch[: self._settings.WATCHLIST_MAX]
        self._store.record_scan(
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        self.last_scan_info = {
            "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "duration_s": round(time.time() - scan_t0, 1),
            "scanned": len(results),
            "signals": sum(1 for r in results
                           if r.decision is DecisionType.SIGNAL),
            "hourly_candidates": len(candidates),
            "hourly_received": len(hourly),
            "daily_cached": len(daily),
            "watchlist": len(watch),
        }
        if self._commentary is not None:
            self._commentary.maybe_generate(self._regime.regime.value)
        if self._gist is not None:
            self._gist.maybe_sync()
        self.progress = ""
        if blocked_count:
            self.last_scan_info["entry_blocked"] = blocked_count
        log.info(kv(event="coarse_scan_done", scanned=len(results),
                    signals=sum(1 for r in results
                                if r.decision is DecisionType.SIGNAL),
                    watchlist=len(self._watchlist)))
        return results

    def _collect_watch(self, d: Decision, watch: list[dict],
                       hourly_series=None) -> None:
        """Izleme listesi adayi: trend gecmis, yalnizca gec asamada takilmis.
        Phase 2'de bu liste ince taramanin (1 dk quote) girdisi olacak."""
        if d.decision is DecisionType.SIGNAL:
            watch.insert(0, {"symbol": d.symbol, "state": "SIGNAL",
                             "direction": d.direction.value})
            return
        late = {"SETUP", "VOLUME", "RISK_REWARD"}
        if (d.decision is DecisionType.NO_TRADE
                and set(d.failed_filters) <= late and d.failed_filters):
            entry = {"symbol": d.symbol, "state": "CANDIDATE",
                     "blocked_by": d.failed_filters[0],
                     "trend": d.trend_bias.value}
            # Faz 2: SETUP'ta takilan aday icin kirilim tetik seviyesi.
            # Long: son yapinin tepesi (son 2 bar haric 30 barin en yuksegi);
            # short ayna. Ince tarama bu seviyenin kirilmasini canli izler.
            if (d.failed_filters[0] == "SETUP" and hourly_series is not None
                    and len(hourly_series) >= 32):
                df = hourly_series.to_dataframe()
                if d.trend_bias.value == "bullish":
                    entry["direction"] = "LONG"
                    entry["trigger_level"] = round(
                        float(df["high"].iloc[-32:-2].max()), 4)
                elif d.trend_bias.value == "bearish":
                    entry["direction"] = "SHORT"
                    entry["trigger_level"] = round(
                        float(df["low"].iloc[-32:-2].min()), 4)
            watch.append(entry)

    # ------------------------------------------ canli durum (Aksiyon Paneli)
    _LIVE_QUOTE_TTL = 60.0

    def _quote_cached(self, symbol: str) -> float | None:
        """Finnhub 60/dk limitine saygi: sembol basi 60 sn onbellek."""
        if not hasattr(self, "_live_cache"):
            self._live_cache = {}
        ts, price = self._live_cache.get(symbol, (0.0, None))
        if time.time() - ts < self._LIVE_QUOTE_TTL:
            return price
        try:
            price = self._md.get_quote(symbol)
        except Exception:
            price = None
        self._live_cache[symbol] = (time.time(), price)
        return price

    def get_live_status(self) -> list[dict]:
        """Acik golge sinyallerin canli fiyatla durumu + eylem onerisi.
        Kural tabanli oneridir; karar her zaman kullanicinindir."""
        if self._tracker is None or self._md is None:
            return []
        today = self._calendar.now_et().date()
        rows: list[dict] = []
        try:
            open_signals = [s for s in self._tracker.recent_signals(50)
                            if s.get("status") != "CLOSED"]
        except Exception:
            return []
        for sig in open_signals[:20]:
            quote = self._quote_cached(sig["symbol"])
            is_long = sig["direction"] == "LONG"
            row = {"symbol": sig["symbol"], "direction": sig["direction"],
                   "status": sig["status"], "quote": quote,
                   "entry_min": sig["entry_min"], "entry_max": sig["entry_max"],
                   "stop": sig["stop_loss"], "tp1": sig["tp1"],
                   "tp2": sig["tp2"], "time_stop_date": sig.get("time_stop_date"),
                   "fill_price": sig.get("fill_price"),
                   # v3.14: grafikte "sinyal dogdu" / "alim yapildi"
                   # isaretleri ve giris gerekcesi icin
                   "created_utc": sig.get("created_utc"),
                   "signal_ts": sig.get("entry_candle_ts"),
                   "fill_ts": sig.get("fill_ts"),
                   "entry_reason": sig.get("entry_reason"),
                   "setup_type": sig.get("setup_type"),
                   "confidence": sig.get("confidence"),
                   "rr": sig.get("rr"),
                   "smc": _json_or_none(sig.get("smc_tags")),
                   "atr_pct": sig.get("atr_pct"),
                   "atr_rank": sig.get("atr_rank")}
            days_left = None
            if sig.get("time_stop_date"):
                try:
                    ts_date = date.fromisoformat(sig["time_stop_date"])
                    days_left = self._calendar.trading_days_between(today, ts_date)
                except ValueError:
                    pass
            row["time_stop_days_left"] = days_left
            if quote is not None:
                sign = 1 if is_long else -1
                row["dist_stop_pct"] = round(
                    sign * (quote - sig["stop_loss"]) / quote * 100, 2)
                row["dist_tp1_pct"] = round(
                    sign * (sig["tp1"] - quote) / quote * 100, 2)
                fill = sig.get("fill_price")
                if sig["status"] == "FILLED" and fill:
                    risk = abs(fill - sig["stop_loss"]) or 1e-9
                    row["r_now"] = round(sign * (quote - fill) / risk, 2)
            row["action"] = self._live_action(row, is_long)
            rows.append(row)
        return rows

    _INDEX_PULSE_TTL = 60.0

    def index_pulse(self) -> list[dict]:
        """SPY/QQQ canli % degisim (dashboard komut cubugu; 60 sn onbellek)."""
        if self._md is None:
            return []
        if not hasattr(self, "_idx_cache"):
            self._idx_cache = (0.0, [])
        ts, cached = self._idx_cache
        if time.time() - ts < self._INDEX_PULSE_TTL:
            return cached
        out = []
        for sym in ("SPY", "QQQ"):
            try:
                q = self._md.get_quote_change(sym)
                if q:
                    out.append({"symbol": sym, **q})
            except Exception:
                pass
        self._idx_cache = (time.time(), out)
        return out

    @staticmethod
    def _live_action(row: dict, is_long: bool) -> str:
        quote, status = row.get("quote"), row.get("status")
        days_left = row.get("time_stop_days_left")
        if quote is None:
            return "fiyat alinamadi"
        if status == "FILLED":
            stop_hit = quote <= row["stop"] if is_long else quote >= row["stop"]
            tp1_hit = quote >= row["tp1"] if is_long else quote <= row["tp1"]
            if stop_hit:
                return "STOP IHLALI - cikisi degerlendir"
            if tp1_hit:
                return "TP1 asildi - kar realizasyonu / stop'u girise cek"
            if row.get("dist_tp1_pct") is not None and row["dist_tp1_pct"] <= 1.0:
                return "TP1'e cok yakin - kismi kar planini hazirla"
            if days_left is not None and days_left <= 0:
                return "TIME-STOP doldu - kapanisa kadar cikis"
            if days_left == 1:
                return "time-stop yarin - hedefe yurumuyorsa cikisa hazirlan"
            return "izle - plan gecerli"
        # PENDING
        in_zone = row["entry_min"] <= quote <= row["entry_max"]
        if in_zone:
            return "GIRIS BOLGESINDE - emir firsati"
        ran_away = quote > row["entry_max"] * 1.02 if is_long             else quote < row["entry_min"] * 0.98
        if ran_away:
            return "bolgeden uzaklasti - KOVALAMAK YOK"
        return "girise gelmesi bekleniyor"

    # ------------------------------------------------- seans fazi + takvim
    def session_info(self, now_et: datetime | None = None) -> dict:
        now_et = now_et or self._calendar.now_et()
        today = now_et.date()
        session = self._calendar.session_times(today)
        info: dict = {"is_trading_day": session is not None}
        if session:
            open_dt, close_dt = session
            if now_et < open_dt:
                info.update(phase="PRE", next_event="acilis",
                            next_event_ms=int(open_dt.timestamp() * 1000))
            elif now_et < close_dt:
                info.update(phase="ACIK", next_event="kapanis",
                            next_event_ms=int(close_dt.timestamp() * 1000))
            else:
                session = None  # bugunku seans bitti -> sonraki acilisi bul
                info["phase"] = "KAPALI"
        if session is None:
            info.setdefault("phase", "KAPALI")
            probe = today
            for _ in range(10):
                probe = probe + timedelta(days=1)
                nxt = self._calendar.session_times(probe)
                if nxt:
                    info.update(next_event="acilis",
                                next_event_ms=int(nxt[0].timestamp() * 1000))
                    break
        return info

    def build_calendar_strip(self, days: int = 5) -> list[dict]:
        """Onumuzdeki N islem gunu: time-stop dolumlari, bilancolar, erken
        kapanislar - 'carsamba cakismasi' onceden gorulsun."""
        today = self._calendar.now_et().date()
        time_stops: dict[str, list[str]] = {}
        if self._tracker is not None:
            try:
                for s in self._tracker.recent_signals(50):
                    if s.get("status") != "CLOSED" and s.get("time_stop_date"):
                        time_stops.setdefault(
                            s["time_stop_date"], []).append(s["symbol"])
            except Exception:
                pass
        watch_syms = list(dict.fromkeys(
            [s for lst in time_stops.values() for s in lst]
            + [w["symbol"] for w in self._watchlist]))[:40]
        earnings: dict[str, list[str]] = {}
        if self._earnings is not None:
            for symbol in watch_syms:
                try:
                    info = self._earnings.info(symbol, today)
                    if info.next_date:
                        earnings.setdefault(info.next_date, []).append(symbol)
                except Exception:
                    continue

        strip: list[dict] = []
        probe = today
        while len(strip) < days:
            session = self._calendar.session_times(probe)
            iso = probe.isoformat()
            if session:
                _, close_dt = session
                strip.append({
                    "date": iso, "weekday": probe.strftime("%a"),
                    "early_close": close_dt.hour < 16,
                    "time_stops": time_stops.get(iso, []),
                    "earnings": earnings.get(iso, []),
                })
            elif probe.weekday() < 5:
                strip.append({"date": iso, "weekday": probe.strftime("%a"),
                              "holiday": True})
            probe = probe + timedelta(days=1)
            if (probe - today).days > 14:
                break
        return strip

    def _portfolio_cap_reason(self, d=None) -> str | None:
        """Portfoy ISI motoru (P1): toplam + gunluk + AYNI-YON + KUME
        tavanlari. 30 Tem dersinin kodlanmis hali: 'hepsi long, hepsi ayni
        gun' defteri bir daha kurulamaz. Motor sinyali uretir (veri setine
        kaydedilir, blocked=2 kohortunda izlenir) ama takip/bildirim yapilmaz."""
        s = self._settings
        if self._tracker is not None and \
                self._tracker.open_count() >= s.MAX_OPEN_SIGNALS:
            return f"eszamanli tavan ({s.MAX_OPEN_SIGNALS})"
        if len(self._signals_today) >= s.MAX_DAILY_SIGNALS:
            return f"gunluk tavan ({s.MAX_DAILY_SIGNALS})"
        if d is not None and self._tracker is not None:
            direction = d.direction.value
            if self._tracker.open_count_by(direction) >= s.MAX_DIR_SIGNALS:
                return f"yon tavani ({direction} {s.MAX_DIR_SIGNALS})"
            from app.services.signal_tracker import _cluster_id
            if self._tracker.open_count_cluster(
                    _cluster_id(d)) >= s.MAX_CLUSTER_SIGNALS:
                return f"kume tavani ({s.MAX_CLUSTER_SIGNALS}/gun/yon)"
        return None

    # ---------------------------------------- seans korumasi (v3.9)
    def _kick_strategy_lab(self) -> None:
        """Aday stratejileri ARKA PLANDA kos. 300 sembol x ~1400 bar
        hesabi tick dongusunde saniyeler surer; haber vakasindan
        ogrendik: islem-kritik akisi ASLA bloklamayiz. Ayni anda tek
        kosum, gunde bir kez."""
        import threading
        if getattr(self, "_slab_running", False):
            return
        today = self._calendar.now_et().date().isoformat()
        if getattr(self, "_slab_date", None) == today:
            return
        snapshot = dict(self._daily_cache)     # kosum sirasinda degismesin

        def _work():
            try:
                # v4.4: onbellek bosken KENDI VERISINI CEKMEZ. Eskiden
                # cekiyordu ve bu, gunluk verinin IKINCI bir kopyasini
                # bellekte tutuyordu; 512 MB'lik Render orneginde servis
                # OOM ile yeniden basladi (4 Agu, 25 dk icinde 2 restart).
                # Artik ilk taramanin onbellegi doldurmasi beklenir.
                if not snapshot:
                    return
                self._strategy_lab.run(snapshot)
                self._slab_date = today
            except Exception:
                log.exception(kv(event="strategy_lab_error"))
            finally:
                self._slab_running = False

        self._slab_running = True
        threading.Thread(target=_work, daemon=True,
                         name="strategy-lab").start()

    def _atr_pcts(self, daily: dict) -> dict[str, tuple]:
        """Sembol -> (ATR yuzdesi, evren icindeki yuzdelik dilim).

        v4.6: 4 Agu gozlemi - acik pozisyonlarimizin TAMAMI evren
        ortancasinin altinda/civarinda oynakliktaydi (%2.2-3.7 vs
        ortanca %3.46). Filtrelerimiz dogal olarak sakin hisseleri
        seciyor olabilir; bu iyi de olabilir kotu de. Sinyal basina
        kaydedip kohort dolunca KENDI defterimizden soracagiz:
        "oynak hisselerdeki sinyaller daha mi iyiydi?"
        SALT OLCUM - karara karismaz.
        """
        from app.services.strategy_lab import atr as _atr
        vals: dict[str, float] = {}
        for sym, series in daily.items():
            cs = series.candles
            if len(cs) < 20:
                continue
            bars = [{"high": c.high, "low": c.low, "close": c.close}
                    for c in cs[-40:]]
            a14 = _atr(bars)
            last, px = a14[-1], bars[-1]["close"]
            if last and px:
                vals[sym] = round(100 * last / px, 3)
        if len(vals) < 30:
            return {}
        ordered = sorted(vals.values())
        n = len(ordered)
        import bisect
        return {sym: (v, round(bisect.bisect_left(ordered, v) / (n - 1), 3))
                for sym, v in vals.items()}

    def _momentum_pcts(self, daily: dict) -> dict[str, float]:
        """12-1 momentum yuzdeligi (kesitsel). 253+ gunluk bari olan
        semboller uzerinden; kisa gecmisliler haric (None kalir)."""
        vals = {}
        for sym, series in daily.items():
            cs = series.candles
            if len(cs) >= 253:
                vals[sym] = cs[-22].close / cs[-253].close - 1
        if len(vals) < 30:
            return {}
        ordered = sorted(vals.values())
        n = len(ordered)
        import bisect
        return {sym: round(bisect.bisect_left(ordered, v) / (n - 1), 3)
                for sym, v in vals.items()} if n > 1 else {}

    def _minutes_since_open(self, now_et: datetime | None = None) -> float | None:
        """Acilistan bu yana gecen dakika; seans gunu degilse None."""
        now_et = now_et or self._calendar.now_et()
        session = self._calendar.session_times(now_et.date())
        if session is None:
            return None
        open_dt, _ = session
        return (now_et - open_dt).total_seconds() / 60.0

    def _index_pcts(self) -> tuple[float | None, float | None]:
        """SPY/QQQ onceki kapanisa gore % (index_pulse 60 sn onbellekli;
        ek API butcesi yok - dashboard cipiyle ayni kaynak)."""
        pulse = {p.get("symbol"): p for p in self.index_pulse()}
        spy = (pulse.get("SPY") or {}).get("pct")
        qqq = (pulse.get("QQQ") or {}).get("pct")
        return spy, qqq

    def _entry_block(self, d: Decision) -> tuple[str, int] | None:
        """YENI giris icin TEKIL karar noktasi (v3.9): (sebep, blocked
        sinifi) dondurur; None = giris serbest. Siralama: kill-switch (3)
        -> acilis penceresi (4) -> portfoy tavani (2). maybe_track'ten
        ONCE cagrilmasi sarttir - tavan sayimlari mevcut satirlari
        saymali, sinyalin kendi eklenmis kaydini DEGIL (cift kayit
        bug'inin duzeltmesi, 2 Agu)."""
        s = self._settings
        if s.INDEX_KILL_SWITCH_ENABLED:
            spy, qqq = self._index_pcts()
            if spy is None and qqq is None:
                log.warning(kv(event="kill_switch_no_index_data",
                               symbol=d.symbol))
            verdict = index_kill_switch(d.direction.value, spy, qqq,
                                        s.KILL_SWITCH_SPY_PCT,
                                        s.KILL_SWITCH_QQQ_PCT)
            if not verdict.allowed:
                return verdict.reason, BLOCKED_KILL_SWITCH
        if d.setup_type is SetupType.BREAKOUT_RETEST and in_open_blackout(
                self._minutes_since_open(), s.BREAKOUT_OPEN_BLACKOUT_MIN):
            return (f"acilis penceresi (ilk {s.BREAKOUT_OPEN_BLACKOUT_MIN} "
                    f"dk breakout yok)", BLOCKED_OPEN_BLACKOUT)
        cap = self._portfolio_cap_reason(d)
        if cap:
            return cap, BLOCKED_PORTFOLIO
        return None

    def guard_info(self) -> dict:
        """Diag/nabiz icin koruma durumu (salt okuma)."""
        s = self._settings
        spy, qqq = self._index_pcts() if s.INDEX_KILL_SWITCH_ENABLED else (None, None)
        mins = self._minutes_since_open()
        return {
            "kill_switch": {
                "enabled": s.INDEX_KILL_SWITCH_ENABLED,
                "spy_thresh_pct": s.KILL_SWITCH_SPY_PCT,
                "qqq_thresh_pct": s.KILL_SWITCH_QQQ_PCT,
                "spy_pct": spy, "qqq_pct": qqq,
                "long_blocked": not index_kill_switch(
                    "LONG", spy, qqq, s.KILL_SWITCH_SPY_PCT,
                    s.KILL_SWITCH_QQQ_PCT).allowed,
                "short_blocked": not index_kill_switch(
                    "SHORT", spy, qqq, s.KILL_SWITCH_SPY_PCT,
                    s.KILL_SWITCH_QQQ_PCT).allowed,
            },
            "open_blackout": {
                "minutes": s.BREAKOUT_OPEN_BLACKOUT_MIN,
                "minutes_since_open": round(mins, 1) if mins is not None else None,
                "active": in_open_blackout(mins, s.BREAKOUT_OPEN_BLACKOUT_MIN),
            },
        }

    def golive_status(self) -> dict:
        """Yazili go-live kriterine gore ilerleme (konsey #3).
        Kriter docs/go-live-kriteri.md'de; esikler settings'te."""
        s = self._settings
        out = {"criteria": {
            "decided": {"min": s.GOLIVE_MIN_DECIDED, "now": 0, "ok": False},
            "clusters": {"min": s.GOLIVE_MIN_CLUSTERS, "now": 0, "ok": False},
            "max_cluster_share": {"max": s.GOLIVE_MAX_CLUSTER_SHARE,
                                  "now": None, "ok": True},
            "expectancy_r": {"min": s.GOLIVE_MIN_EXPECTANCY_R, "now": None,
                             "ok": False},
            "max_dd_r": {"max": s.GOLIVE_MAX_DD_R, "now": None, "ok": True},
        }, "met": False}
        if self._tracker is None:
            return out
        try:
            lock = s.CONFIG_LOCK_UTC
            out["cohort_since"] = lock
            nt = self._tracker.net_totals(since_utc=lock)
            decided = nt["decided"]
            c = out["criteria"]
            c["decided"]["now"] = decided
            c["decided"]["ok"] = decided >= s.GOLIVE_MIN_DECIDED
            if decided:
                exp = nt.get("net_expectancy")
                c["expectancy_r"]["now"] = exp
                c["expectancy_r"]["ok"] = (exp is not None
                                           and exp >= s.GOLIVE_MIN_EXPECTANCY_R)
            c["expectancy_r"]["basis"] = "net"
            cs = self._tracker.cluster_stats(since_utc=lock)
            c["clusters"]["now"] = cs["clusters"]
            c["clusters"]["ok"] = cs["clusters"] >= s.GOLIVE_MIN_CLUSTERS
            share = cs["max_cluster_share"]
            c["max_cluster_share"]["now"] = share
            c["max_cluster_share"]["ok"] = (
                share is None or share <= s.GOLIVE_MAX_CLUSTER_SHARE)
            dd = self._tracker.max_drawdown_r(since_utc=lock)
            c["max_dd_r"]["now"] = dd
            c["max_dd_r"]["ok"] = dd <= s.GOLIVE_MAX_DD_R
            out["met"] = all(v["ok"] for v in c.values())
        except Exception:
            log.exception(kv(event="golive_status_error"))
        return out

    def benchmark_info(self) -> dict | None:
        """Ayni donem SPY al-tut getirisi (konsey: 'beta mi alfa mi').
        Donem = ilk sinyal tarihinden bugune; SPY kapanislari gunluk cache'ten."""
        if self._tracker is None:
            return None
        try:
            first = self._tracker.first_signal_utc()
            if not first or _BENCH not in (self._daily_cache or {}):
                return None
            df = self._daily_cache[_BENCH].to_dataframe()
            start_date = first[:10]
            if hasattr(df.index, "strftime"):
                window = df[df.index.strftime("%Y-%m-%d") >= start_date]
            else:                       # sentetik veri (testler): tum seri
                window = df
            if len(window) < 1:
                return None
            first_close = float(window["close"].iloc[0])
            last_close = float(df["close"].iloc[-1])
            return {"since": start_date,
                    "spy_return_pct": round((last_close / first_close - 1) * 100, 2)}
        except Exception:
            log.exception(kv(event="benchmark_error"))
            return None

    def build_eod_extras(self) -> str:
        """Konsey eklentileri: SPY kiyasi, setup dengesi, dolum kalitesi."""
        if self._tracker is None:
            return ""
        lines = []
        bench = self.benchmark_info()
        if bench:
            lines.append(f"SPY ayni donem ({bench['since']}'den beri): "
                         f"{bench['spy_return_pct']:+.2f}%")
        try:
            mix = self._tracker.setup_mix()
            if mix["setup"]:
                st = " / ".join(f"{k}:{v}" for k, v in
                                sorted(mix["setup"].items()))
                cf = " / ".join(f"{k}:{v}" for k, v in
                                sorted(mix["confidence"].items()))
                line = f"Setup dagilimi: {st} | Guven: {cf}"
                total = sum(mix["setup"].values())
                top = max(mix["setup"].values())
                if total >= 5 and top / total >= 0.8:
                    line += " (tek kanat calisiyor - izlemede)"
                lines.append(line)
        except Exception:
            log.exception(kv(event="eod_mix_error"))
        try:
            nt_all = self._tracker.net_totals()
            nt_lock = self._tracker.net_totals(
                since_utc=self._settings.CONFIG_LOCK_UTC)
            if nt_all["decided"]:
                lines.append(
                    f"Toplam R brut/NET: {nt_all['gross_r']:+.2f} / "
                    f"{nt_all['net_r']:+.2f} (tum kohortlar) | "
                    f"KILIT kohortu: {nt_lock['decided']} islem, "
                    f"NET {nt_lock['net_r']:+.2f}R")
            bs = self._tracker.blocked_summary()
            if bs["total"]:
                lines.append(f"Tavan kohortu: {bs['total']} sinyal "
                             f"({bs['open']} izleniyor) | kacirilanin "
                             f"varsayimsal toplami {bs['hypo_r']:+.2f}R")
        except Exception:
            log.exception(kv(event="eod_net_error"))
        try:
            wsyms = set((self.wallet or {}).keys())
            if wsyms:
                hits = [s for s in self._tracker.open_symbols() if s in wsyms]
                if hits:
                    lines.append("Cuzdan kesisimi (acik sinyalli): " + ", ".join(sorted(hits)))
        except Exception:
            pass
        try:
            g = self.golive_status()
            c = g["criteria"]
            exp = c["expectancy_r"]["now"]
            lines.append(
                f"Go-live kriteri: {c['decided']['now']}/{c['decided']['min']} "
                f"sonuclanan | beklenti "
                f"{exp if exp is not None else '-'}R"
                f"/{c['expectancy_r']['min']}R | maksDD "
                f"{c['max_dd_r']['now'] if c['max_dd_r']['now'] is not None else '-'}R"
                f"/{c['max_dd_r']['max']}R -> "
                f"{'KARSILANDI' if g['met'] else 'henuz degil'}")
        except Exception:
            log.exception(kv(event="eod_golive_error"))
        try:
            cmp_svc = getattr(self, "data_comparison", None)
            if cmp_svc is not None and cmp_svc.enabled:
                line = cmp_svc.summary_line()
                if line:
                    lines.append(line)
        except Exception:
            log.exception(kv(event="eod_datacmp_error"))
        try:
            pb = [b for b in self._tracker.phase_breakdown(
                since_utc=self._settings.CONFIG_LOCK_UTC) if b["n"] >= 3]
            if pb:
                parts = [f"{b['phase']} {b['n']}i {b['net_expectancy']:+.2f}R"
                         for b in pb[:4]]
                lines.append("Seans fazi (>=3 islem): " + " | ".join(parts))
        except Exception:
            log.exception(kv(event="eod_phase_error"))
        try:
            fq = self._tracker.fill_quality()
            if fq:
                lines.append(f"Dolum kalitesi ({fq['n']} poz): "
                             f"MFE medyan {fq['mfe_median']:+.2f}R | "
                             f"MAE medyan {fq['mae_median']:+.2f}R | "
                             f"en derin {fq['worst']}")
        except Exception:
            log.exception(kv(event="eod_quality_error"))
        return ("\n".join(lines) + "\n") if lines else ""

    def _maybe_compare_data(self, today) -> None:
        """Gunde bir kez yfinance<->Alpaca karsilastirmasi (salt gozlem).
        Motor kararlarina etkisi yoktur; amac ana kaynagi degistirmeden
        once Alpaca'nin guvenilirligini olcmek (Asama 0)."""
        cmp_svc = getattr(self, "data_comparison", None)
        if cmp_svc is None or not cmp_svc.enabled or self._datacmp_date == today:
            return
        self._datacmp_date = today
        try:
            symbols = self._universe.get_symbols() if self._universe else []
            if symbols:
                cmp_svc.compare(symbols, "1d")
        except Exception:
            log.exception(kv(event="datacmp_tick_error"))

    def _wallet_note(self, symbol: str) -> str:
        qty = (self.wallet or {}).get(symbol)
        return f" • cüzdanında {qty} adet" if qty else ""

    def build_weekly_report(self) -> str | None:
        """Pazar aksami haftalik ozet (oneri #4)."""
        if self._tracker is None:
            return None
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)) \
            .strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = [r for r in self._tracker.recent_signals(300)
                if r.get("status") == "CLOSED" and (r.get("closed_utc") or "") >= cutoff
                and r.get("outcome") in ("WIN", "LOSS", "EXPIRED")]
        lines = ["HAFTALIK RAPOR (son 7 gun)"]
        if rows:
            tot = sum(r.get("r_multiple") or 0 for r in rows)
            net = sum(r.get("r_net", r.get("r_multiple")) or 0 for r in rows)
            wins = sum(1 for r in rows if (r.get("r_multiple") or 0) > 0)
            best = max(rows, key=lambda r: r.get("r_multiple") or 0)
            worst = min(rows, key=lambda r: r.get("r_multiple") or 0)
            lines += [
                f"Sonuclanan: {len(rows)} ({wins} kazanc) | "
                f"Toplam {tot:+.2f}R | NET {net:+.2f}R",
                f"En iyi: {best['symbol']} {best.get('r_multiple'):+.2f}R | "
                f"En kotu: {worst['symbol']} {worst.get('r_multiple'):+.2f}R"]
        else:
            lines.append("Bu hafta sonuclanan islem yok.")
        g = self.golive_status()
        c = g["criteria"]
        lines.append(f"Kilit kohortu: {c['decided']['now']}/{c['decided']['min']} "
                     f"sonuclanan -> {'KARSILANDI' if g['met'] else 'devam'}")
        if self._tracker.open_count():
            lines.append(f"Acik sinyal: {self._tracker.open_count()}")
        bench = self.benchmark_info()
        if bench:
            lines.append(f"SPY ayni donem: {bench['spy_return_pct']:+.2f}%")
        return "\n".join(lines)

    def _maybe_weekly(self, now_et) -> None:
        if now_et.weekday() == 6 and now_et.hour >= 14 \
                and self._weekly_date != now_et.date():
            self._weekly_date = now_et.date()
            try:
                text = self.build_weekly_report()
                if text:
                    self._send(text)
            except Exception:
                log.exception(kv(event="weekly_report_error"))

    def _deadman_check(self, now_et, open_dt, today) -> None:
        """Dead-man switch (P1): seans acikken taramalar N dakikadan uzun
        sustuysa gunde bir kez Telegram alarmi. Amac: 'bot calisiyor
        saniyorduk' vakalarinin (uyku/askı/veri kilidi) SESSIZ kalmamasi."""
        limit_min = self._settings.DEADMAN_SCAN_STALENESS_MIN
        if (now_et - open_dt).total_seconds() < limit_min * 60:
            return                      # seans yeni acildi, tarama hakki taninir
        if self._deadman_date == today:
            return
        last_ts = (self.last_scan_info or {}).get("ts_utc")
        stale = True
        if last_ts:
            try:
                dt = datetime.strptime(last_ts, "%Y-%m-%dT%H:%M:%SZ") \
                    .replace(tzinfo=timezone.utc)
                stale = (datetime.now(timezone.utc) - dt).total_seconds() \
                    > limit_min * 60
            except ValueError:
                pass
        if stale:
            self._deadman_date = today
            log.error(kv(event="deadman_alert", last_scan=last_ts))
            self._send(
                f"DEAD-MAN UYARISI | Seans acik ama {limit_min} dk'dan uzun "
                f"suredir tarama yok (son: {last_ts or 'hic'}).\n"
                f"Olasi nedenler: veri kaynagi kilidi, dongu hatasi, servis "
                f"sorunu. Dashboard/loglari kontrol et.")

    def build_heartbeat(self) -> dict:
        """Uzaktan izleme nabzi: saglik ozetinin tamami tek JSON'da."""
        from app.logging_setup import get_ring_buffer
        ring = get_ring_buffer()
        hb = {
            "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "uptime_min": ring.uptime_sec() // 60,
            "progress": self.progress,
            "regime": self._regime.regime.value,
            "last_prep": self.last_prep_info,
            "last_scan": self.last_scan_info,
            "fine_scan": self.last_fine_info,
            "gap_watch": self.last_gap_watch,
            "watchlist_size": len(self._watchlist),
            "log_counts": dict(ring.counts),
            "golive": self.golive_status(),
            "recent_warnings": ring.recent(25),
        }
        try:
            hb["universe_count"] = (self._universe.describe() or {}).get(
                "filtered_count")
        except Exception:
            hb["universe_count"] = None
        if self._tracker is not None:
            try:
                st = self._tracker.stats()
                hb["shadow"] = {k: st[k] for k in
                                ("open_signals", "decided_trades",
                                 "total_r_multiple")}
            except Exception:
                hb["shadow"] = None
        return hb

    def _news_symbols(self) -> list[str]:
        """Haber akisi kapsami: acik golge pozisyonlar + bugunun sinyalleri
        + izleme listesi adaylari (rotasyonla taranir)."""
        symbols: list[str] = []
        if self._tracker is not None:
            try:
                symbols += [s["symbol"] for s in
                            self._tracker.recent_signals(50)
                            if s.get("status") != "CLOSED"]
            except Exception:
                pass
        symbols += [t.split(" ")[0] for t in self._signals_today]
        symbols += [w["symbol"] for w in self._watchlist]
        return list(dict.fromkeys(symbols))

    # -------------------------------------------------- Faz 2: ince tarama
    def run_fine_scan(self) -> None:
        """~1 dk'da bir canli fiyat yoklamasi (plan bolum 5, Faz 2):
        1) PENDING sinyalin fiyati giris bolgesine girdi -> ani bildirim
        2) SETUP'ta takilan adayin kirilim seviyesi asildi -> aninda tam
           yeniden degerlendirme (1h tek sembol) -> SIGNAL ise dispatch.
        Sinyal gecikmesi <=15 dk'dan ~1 dk'ya iner."""
        if self._tracker is None:
            return
        checked = zone_hits = trigger_hits = 0
        budget = self._settings.FINE_MAX_SYMBOLS

        # --- 1) bekleyen sinyaller: bolgeye giris ani ---
        pending = [s for s in self._tracker.recent_signals(50)
                   if s.get("status") == "PENDING"][:budget]
        for sig in pending:
            quote = self._quote_cached(sig["symbol"])
            if quote is None:
                continue
            checked += 1
            if sig["entry_min"] <= quote <= sig["entry_max"]                     and sig["id"] not in self._zone_notified:
                self._zone_notified.add(sig["id"])
                zone_hits += 1
                self._send(
                    f"GIRIS TETIKLENDI | {sig['symbol']} {sig['direction']}"
                    f"{self._wallet_note(sig['symbol'])}\n"
                    f"Canli fiyat {quote:g} giris bolgesinde "
                    f"({sig['entry_min']:g} - {sig['entry_max']:g}).\n"
                    f"Plan: stop {sig['stop_loss']:g} | TP1 {sig['tp1']:g} | "
                    f"TP2 {sig['tp2']:g}\n"
                    f"Emir Midas'tan manuel girilir; LIMIT emir onerilir.")
                log.info(kv(event="fine_zone_touch", symbol=sig["symbol"],
                            quote=quote))

        # --- 2) adaylar: kirilim tetigi -> aninda tam degerlendirme ---
        # v3.9 acilis penceresi: ilk N dk kirilim tetigi CALISMAZ (acilis
        # fake'leri; 29 Tem 13:30 salvosu). Bolge tetigi (1) etkilenmez.
        blackout = in_open_blackout(self._minutes_since_open(),
                                    self._settings.BREAKOUT_OPEN_BLACKOUT_MIN)
        armed = [w for w in self._watchlist
                 if w.get("state") == "CANDIDATE" and w.get("trigger_level")]
        if blackout and armed:
            log.info(kv(event="fine_trigger_blackout", armed=len(armed)))
        for w in ([] if blackout else armed)[: max(0, budget - checked)]:
            quote = self._quote_cached(w["symbol"])
            if quote is None:
                continue
            checked += 1
            buf = 1 + self._settings.FINE_TRIGGER_BUFFER_PCT / 100
            crossed = (quote >= w["trigger_level"] * buf
                       if w.get("direction") == "LONG"
                       else quote <= w["trigger_level"] / buf)
            if not crossed:
                continue
            now = time.time()
            if now - self._reeval_at.get(w["symbol"], 0) <                     self._settings.FINE_REEVAL_COOLDOWN_SEC:
                continue
            self._reeval_at[w["symbol"]] = now
            trigger_hits += 1
            log.info(kv(event="fine_trigger", symbol=w["symbol"],
                        level=w["trigger_level"], quote=quote))
            try:
                self._fine_reevaluate(w["symbol"])
            except Exception:
                log.exception(kv(event="fine_reeval_error", symbol=w["symbol"]))

        self.last_fine_info = {
            "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "checked": checked, "zone_hits": zone_hits,
            "trigger_hits": trigger_hits,
            "pending": len(pending), "armed": len(armed),
            "open_blackout": blackout}

    def _fine_reevaluate(self, symbol: str) -> None:
        """Kirilim ani icin tek sembolluk tam pipeline kosusu."""
        today = self._calendar.now_et().date()
        daily = self._daily_cache if self._daily_cache_date == today else {}
        if symbol not in daily:
            return
        hourly = self._md.get_hourly_bulk([symbol]).get(symbol)
        if hourly is None:
            return
        bench_df = (daily[_BENCH].to_dataframe()
                    if _BENCH in daily else None)
        e_info = self._earnings.info(symbol, today)
        d = signal_engine.evaluate(symbol, daily.get(symbol),
                                   hourly.closed_only(),
                                   self._regime, self._params, bench_df, e_info)
        if d.decision is DecisionType.SIGNAL:
            block = self._entry_block(d)
            if block is not None:
                log.info(kv(event="entry_blocked", symbol=symbol,
                            blocked_class=block[1], reason=block[0],
                            source="fine"))
                if self._tracker is not None:
                    try:
                        self._tracker.track_blocked(
                            d, hourly, block[0], block[1])
                    except Exception:
                        log.exception(kv(event="blocked_track_error",
                                         symbol=symbol))
                return
            d.time_stop_date = self._calendar.add_trading_days(
                today, self._params.time_stop_days).isoformat()
            d.session_phase = self._calendar.session_phase()
            if self._tracker is not None:
                self._tracker.record_candles(hourly)
                self._tracker.record_decision(d)
                self._tracker.maybe_track(d, hourly)
                self._tracker.evaluate_open(symbol)
            self._store.save_result(symbol, d.contract_dict())
            self._dispatch(d)
            log.info(kv(event="fine_signal", symbol=symbol,
                        direction=d.direction.value))

    # ------------------------------------------------- acilis oncesi gap nobeti
    def run_gap_watch(self, today: date) -> None:
        """Acik pozisyonlar + guclu adaylar icin pre-market quote kontrolu.
        Sinyal URETMEZ; yalnizca gap istihbarati (onayli plan eki)."""
        self._gap_watch_date = today
        if self._tracker is None:
            return
        try:
            open_signals = [s for s in self._tracker.recent_signals(100)
                            if s.get("status") != "CLOSED"]
            candidates = [w["symbol"] for w in self._watchlist
                          if w.get("state") == "CANDIDATE"]
            pos_syms = [s["symbol"] for s in open_signals]
            budget = self._settings.PREMARKET_MAX_SYMBOLS
            symbols = list(dict.fromkeys(
                pos_syms + candidates))[:budget]
            candidates = [s for s in symbols if s not in pos_syms]
            if not symbols:
                log.info(kv(event="gap_watch_skip", reason="izlenecek sembol yok"))
                return

            quotes: dict[str, float] = {}
            for symbol in symbols:
                q = self._md.get_quote(symbol)
                if q is not None:
                    quotes[symbol] = q
            daily = self._get_daily_cached(symbols, today)
            prev_closes = {s: daily[s].candles[-1].close
                           for s in symbols if s in daily and len(daily[s])}

            # v3.17: ACIK POZISYONLARIN quote'u alinamadiysa SESSIZ KALMA.
            # Bilanco vakasiyla ayni hastalik: koruyucu kontrol sessizce
            # atlaniyordu. Pozisyon gece stop'unun otesinde acilmis
            # olabilir ve haberimiz olmaz. Aday sembollerde sessizlik
            # kabul (onlar sadece firsat), POZISYONLARDA degil.
            pos_syms = {str(x.get("symbol")) for x in open_signals}
            missing_pos = sorted(pos_syms - set(quotes))
            if missing_pos:
                log.error(kv(event="gap_watch_quote_missing",
                             symbols=",".join(missing_pos)))
                self._send("UYARI: gap nobetinde fiyat alinamadi -> "
                           + ", ".join(missing_pos)
                           + ". Bu pozisyonlar KONTROL EDILEMEDI, "
                             "acilista kendiniz bakin.")
            report = premarket_watch.build_gap_report(
                open_signals, candidates, quotes, prev_closes,
                self._settings.PREMARKET_GAP_ALERT_PCT)
            self.last_gap_watch = {
                "date": today.isoformat(), "checked": report["checked"],
                "quotes_received": len(quotes),
                "positions_unchecked": missing_pos,
                "position_alerts": report["position_alerts"],
                "candidate_alerts": report["candidate_alerts"]}
            text = premarket_watch.render_gap_report(report)
            if text:
                self._send(text)
            log.info(kv(event="gap_watch_done", symbols=len(symbols),
                        quotes=len(quotes),
                        alerts=len(report["position_alerts"])
                        + len(report["candidate_alerts"])))
        except Exception:
            log.exception(kv(event="gap_watch_error"))

    def _evaluate_orphans(self, scanned: set) -> None:
        """Evren disina dusen sembollerin acik sinyallerini yasat (bybit v3.0
        'IONQ vakasi' portu): sembol likidite filtresinden cikinca taranmiyor,
        acik golge sinyali sonsuza dek PENDING/FILLED kaliyordu. Artik her tur
        sonunda taranmamis acik-sinyalli semboller icin 1h mum cekilir ve
        degerlendirme calistirilir."""
        try:
            orphans = [s for s in self._tracker.open_symbols()
                       if s not in scanned]
        except Exception:
            log.exception(kv(event="orphan_list_error"))
            return
        if not orphans:
            return
        try:
            hourly = self._md.get_hourly_bulk(orphans)
        except Exception:
            log.exception(kv(event="orphan_fetch_error"))
            return
        for symbol in orphans:
            try:
                if symbol in hourly and len(hourly[symbol]):
                    self._tracker.record_candles(hourly[symbol])
                self._tracker.evaluate_open(symbol)
                log.info(kv(event="orphan_eval", symbol=symbol))
            except Exception:
                log.exception(kv(event="orphan_eval_error", symbol=symbol))

    # ---------------------------------------------------------- gun sonu ozeti
    def run_eod(self, today: date) -> None:
        # v3.19: cikis laboratuvari - ayni sinyaller, paralel cikislar
        if self._exit_lab is not None:
            try:
                self._exit_lab.run(today)
            except Exception:
                log.exception(kv(event="exit_lab_error"))
        self._kick_strategy_lab()
        self._eod_date = today
        watch_txt = ", ".join(w["symbol"] for w in self._watchlist[:15]) or "-"
        shadow_line = ""
        if self._tracker is not None:
            try:
                st = self._tracker.stats()
                wr = (f"%{st['win_rate'] * 100:.0f}" if st["win_rate"] is not None
                      else "-")
                shadow_line = (f"Golge takip: {st['open_signals']} acik | "
                               f"{st['decided_trades']} sonuclanan | "
                               f"WR {wr} | Toplam {st['total_r_multiple']:+.2f}R\n")
            except Exception:
                log.exception(kv(event="eod_stats_error"))
        eod_comment = ""
        if self._commentary is not None:
            try:
                row = self._commentary.generate(self._regime.regime.value)
                eod_comment = f"\n\nBot degerlendirmesi:\n{row['text']}"
            except Exception:
                log.exception(kv(event="eod_commentary_error"))
        if self._settings.SEND_EOD_SUMMARY:
            self._send(
                f"Gun sonu ozeti ({today.isoformat()})\n"
                f"Rejim: {self._regime.regime.value}\n"
                f"Bugunku sinyaller: "
                f"{', '.join(self._signals_today) or 'yok'}\n"
                f"{shadow_line}"
                f"{self.build_eod_extras()}"
                f"Yarin izlenecekler ({len(self._watchlist)}): {watch_txt}\n"
                f"Acik pozisyonlarda time-stop kuralini unutmayin."
                f"{eod_comment}"
            )
        if self._gist is not None:
            try:
                self._gist.sync()   # gun sonunda kosulsuz arsivle
            except Exception:
                log.exception(kv(event="eod_gist_error"))
        log.info(kv(event="eod_done", signals=len(self._signals_today),
                    watchlist=len(self._watchlist)))

    # ------------------------------------------------------------------ dispatch
    def _dispatch(self, d: Decision) -> None:
        if d.decision is DecisionType.SIGNAL:
            if self._store.cooldown_active(d.symbol, d.direction.value,
                                           self._settings.SIGNAL_COOLDOWN_SEC):
                log.info(kv(event="cooldown_skip", symbol=d.symbol,
                            direction=d.direction.value))
                return
            if self._send(telegram_formatter.render(d, self._settings.TELEGRAM_PARSE_MODE)):
                self._store.mark_signal_sent(d.symbol, d.direction.value)
            self._signals_today.append(f"{d.symbol} {d.direction.value}")
        elif d.decision is DecisionType.NO_TRADE and self._settings.SEND_NO_TRADE:
            self._send(telegram_formatter.render(d, self._settings.TELEGRAM_PARSE_MODE))

    def _send(self, text: str) -> bool:
        if not self._settings.TELEGRAM_ENABLED:
            return False  # sessiz mod: uretim surer, mesaj gitmez
        return self._notifier.send(text)

    def _startup_message(self) -> None:
        s = self._settings
        self._send(
            "Midas ABD hisse sinyal botu aktif.\n"
            f"TF: {s.HTF}/{s.MTF} | Kaba tarama: {s.COARSE_SCAN_INTERVAL_SEC // 60} dk\n"
            f"Yon: LONG+SHORT (short icin siki esikler) | Min RR: {s.RISK_REWARD_MIN}\n"
            f"Maliyet filtresi: TP1 >= %{s.MIN_TARGET_PCT} | "
            f"Bilanco blackout: +-{s.EARNINGS_BLACKOUT_DAYS} gun\n"
            f"Golge takip: {'acik' if self._tracker else 'kapali'} | "
            f"Gist yedek: {'acik' if self._gist else 'kapali'}\n"
            "Seans disi ve tatillerde uyur. Emirler Midas'tan manuel girilir."
        )
