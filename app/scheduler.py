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

import logging
import threading
import time
from datetime import date, datetime, timedelta, timezone

from app.config.settings import Settings
from app.formatting import telegram_formatter
from app.integrations.telegram_notifier import TelegramNotifier
from app.logging_setup import kv
from app.models.decision import Decision, DecisionType, MarketRegime
from app.services.earnings_service import EarningsService
from app.services.market_calendar import MarketCalendar
from app.services.market_data_service import MarketDataService
from app.services.state_store import StateStore
from app.services.universe import UniverseProvider
from app.strategies import signal_engine
from app.strategies.regime_detector import RegimeResult, classify_market_regime

log = logging.getLogger("scheduler")

_BENCH = "SPY"


class Scheduler:
    def __init__(self, settings: Settings, market_data: MarketDataService,
                 universe: UniverseProvider, earnings: EarningsService,
                 calendar: MarketCalendar, store: StateStore,
                 notifier: TelegramNotifier, tracker=None,
                 gist_backup=None) -> None:
        self._settings = settings
        self._md = market_data
        self._universe = universe
        self._earnings = earnings
        self._calendar = calendar
        self._store = store
        self._notifier = notifier
        self._tracker = tracker      # None -> golge takip kapali
        self._gist = gist_backup     # None -> gist yedekleme kapali
        self._params = settings.strategy_params

        self._last_coarse = 0.0
        self._daily_cache: dict = {}
        self._daily_cache_date: date | None = None
        self._prep_date: date | None = None
        self._eod_date: date | None = None
        self._regime = RegimeResult(regime=MarketRegime.UNKNOWN, detail="not computed")
        self._watchlist: list[dict] = []
        self._signals_today: list[str] = []
        self.last_scan_info: dict = {}
        self.last_prep_info: dict = {}

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
        session = self._calendar.session_times(today)
        if session is None:
            return  # hafta sonu / tatil: uyu
        open_dt, close_dt = session
        prep_dt = open_dt - timedelta(minutes=self._settings.PREP_LEAD_MIN)
        eod_dt = close_dt + timedelta(minutes=self._settings.EOD_DELAY_MIN)

        if now_et >= prep_dt and self._prep_date != today:
            self.run_prep(today)
        if open_dt <= now_et < close_dt:
            if time.time() - self._last_coarse >= self._settings.COARSE_SCAN_INTERVAL_SEC:
                self.run_coarse_scan(send_telegram=True)
                self._last_coarse = time.time()
        if now_et >= eod_dt and self._eod_date != today and self._prep_date == today:
            self.run_eod(today)

    # ------------------------------------------------------- 15:45 TR hazirlik
    def run_prep(self, today: date) -> None:
        log.info(kv(event="prep_start", date=today.isoformat()))
        self._prep_date = today
        self._signals_today = []
        symbols = self._universe.refresh(force=True)
        self._earnings.refresh(today, force=True)
        self._regime = self._compute_regime()
        self.last_prep_info = {"date": today.isoformat(),
                               "universe": len(symbols),
                               "regime": self._regime.regime.value}
        log.info(kv(event="prep_done", universe=len(symbols),
                    regime=self._regime.regime.value))
        if self._settings.SEND_PREP_SUMMARY:
            self._send(
                f"Hazirlik tamam ({today.isoformat()})\n"
                f"Evren: {len(symbols)} sembol (likidite filtreli)\n"
                f"Rejim: {self._regime.regime.value} ({self._regime.detail})\n"
                f"Kaba tarama seans acilisiyla baslar "
                f"({self._settings.COARSE_SCAN_INTERVAL_SEC // 60} dk aralik)."
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
        daily = self._get_daily_cached(fetch_list, today)

        idx = self._settings.regime_symbols
        spy_df = daily.get(idx[0]).to_dataframe() if idx and idx[0] in daily else None
        qqq_df = (daily.get(idx[1]).to_dataframe()
                  if len(idx) > 1 and idx[1] in daily else None)
        self._regime = classify_market_regime(spy_df, qqq_df)
        bench_df = daily.get(_BENCH).to_dataframe() if _BENCH in daily else None

        # --- 1. gecis: gunluk filtreler (1h verisi olmadan) ---
        pass1: dict[str, Decision] = {}
        candidates: list[str] = []
        for symbol in symbols:
            try:
                e_info = self._earnings.info(symbol, today)
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
        hourly = self._md.get_hourly_bulk(capped) if capped else {}
        results: list[Decision] = []
        watch: list[dict] = []
        for symbol, d in pass1.items():
            try:
                if symbol in hourly:
                    e_info = self._earnings.info(symbol, today)
                    d = signal_engine.evaluate(symbol, daily.get(symbol),
                                               hourly.get(symbol), self._regime,
                                               self._params, bench_df, e_info)
                if d.decision is DecisionType.SIGNAL:
                    d.time_stop_date = self._calendar.add_trading_days(
                        today, self._params.time_stop_days).isoformat()
            except Exception:
                log.exception(kv(event="scan_error", symbol=symbol, stage=2))
                continue
            results.append(d)
            if self._tracker is not None:
                try:
                    if symbol in hourly:
                        self._tracker.record_candles(hourly[symbol])
                    if symbol in daily:
                        self._tracker.record_candles(daily[symbol])
                    self._tracker.record_decision(d)
                    if symbol in hourly:
                        self._tracker.maybe_track(d, hourly[symbol])
                    self._tracker.evaluate_open(symbol)
                except Exception:
                    log.exception(kv(event="tracker_error", symbol=symbol))
            self._store.save_result(symbol, d.contract_dict())
            self._collect_watch(d, watch)
            if send_telegram:
                self._dispatch(d)
            log.info(kv(event="scan", symbol=symbol, decision=d.decision.value,
                        direction=d.direction.value,
                        reason=d.reject_reason or d.setup_type.value))

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
        if self._gist is not None:
            self._gist.maybe_sync()
        log.info(kv(event="coarse_scan_done", scanned=len(results),
                    signals=sum(1 for r in results
                                if r.decision is DecisionType.SIGNAL),
                    watchlist=len(self._watchlist)))
        return results

    def _collect_watch(self, d: Decision, watch: list[dict]) -> None:
        """Izleme listesi adayi: trend gecmis, yalnizca gec asamada takilmis.
        Phase 2'de bu liste ince taramanin (1 dk quote) girdisi olacak."""
        if d.decision is DecisionType.SIGNAL:
            watch.insert(0, {"symbol": d.symbol, "state": "SIGNAL",
                             "direction": d.direction.value})
            return
        late = {"SETUP", "VOLUME", "RISK_REWARD"}
        if (d.decision is DecisionType.NO_TRADE
                and set(d.failed_filters) <= late and d.failed_filters):
            watch.append({"symbol": d.symbol, "state": "CANDIDATE",
                          "blocked_by": d.failed_filters[0],
                          "trend": d.trend_bias.value})

    # ---------------------------------------------------------- gun sonu ozeti
    def run_eod(self, today: date) -> None:
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
        if self._settings.SEND_EOD_SUMMARY:
            self._send(
                f"Gun sonu ozeti ({today.isoformat()})\n"
                f"Rejim: {self._regime.regime.value}\n"
                f"Bugunku sinyaller: "
                f"{', '.join(self._signals_today) or 'yok'}\n"
                f"{shadow_line}"
                f"Yarin izlenecekler ({len(self._watchlist)}): {watch_txt}\n"
                f"Acik pozisyonlarda time-stop kuralini unutmayin."
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
