"""
SignalTracker - golge donemi takip motoru. SESSIZ calisir (Telegram'a yazmaz).
Bybit reposundan tasindi; ABD hisse uyarlamalari:
  - pair -> symbol, 15dk -> 1h bar (fill_window ~2 seans, max_track ~4 seans)
  - GAP MUHASEBESI: hisseler gece gap yapar. Bar stop/TP'nin OTESINDE acilirsa
    cikis stop seviyesinden degil ACILIS fiyatindan sayilir (plan bolum 3:
    "stop kesin calisir varsayilamaz"). Gap-through-stop -1R'den KOTU sonuclanabilir.

Sorumluluklar:
1. Her karari decisions tablosuna kaydet -> backtest etiketi.
2. Her taramada kapanmis mumlari candles tablosuna biriktir (INSERT OR IGNORE).
3. Her SIGNAL'i signals tablosunda izle ve sonraki 1h mumlarla sonuclandir:
     PENDING -> fiyat entry bolgesine girerse FILLED, girmezse NOT_FILLED
     FILLED  -> stop'a deger LOSS, TP1'e deger WIN, ayni mumda ikisi -> AMBIGUOUS,
                sure asarsa EXPIRED (kapanisa gore R)
4. stats() ile basari orani / toplam R hesabi.

Varsayimlar (golge muhasebesi - muhafazakar, dokumante):
- Fill fiyati: LONG'da entry_max, SHORT'ta entry_min (bolgenin ilk degen kenari).
- Ayni mumda hem stop hem TP kesilirse sira bilinemez -> AMBIGUOUS, orana dahil edilmez.
- Tahmini olcumdur; gercek emir doldurma/spread/slippage icermez.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from app.logging_setup import kv
from app.models.candle import KlineSeries
from app.strategies.smc_tags import tag_candles
from app.models.decision import Decision, DecisionType, Direction
from app.services.database import Database

log = logging.getLogger("tracker")

# KONFIG KILIDI (P0): motor kaynak dosyalarinin kisa parmak izi - her sinyal
# hangi motor surumuyle uretildigini tasir; kilit-oncesi/sonrasi kohortlar
# ayri degerlendirilir (docs/config-lock.md).
def _engine_sha() -> str:
    import hashlib
    import os
    base = os.path.join(os.path.dirname(__file__), "..", "strategies")
    h = hashlib.sha256()
    try:
        for name in sorted(os.listdir(base)):
            if name.endswith(".py"):
                with open(os.path.join(base, name), "rb") as f:
                    h.update(f.read())
    except OSError:
        return "unknown"
    return h.hexdigest()[:12]


_ENGINE_SHA = _engine_sha()


def _smc(d, mtf) -> str | None:
    """SMC etiketleri (v3.15) - YALNIZCA METADATA, karara karismaz.
    Hata halinde None; etiket uretilemezse sinyal etkilenmez."""
    try:
        entry = (d.entry_zone.min + d.entry_zone.max) / 2
        tags = tag_candles(mtf.candles, d.direction.value, entry)
        return json.dumps(tags) if tags else None
    except Exception:
        return None


def _entry_reason(d) -> str:
    """Sinyal DOGARKEN 'neden girilmeli' gerekcesini tek cumleye yazar.
    v3.14: sonradan yeniden kurmak yerine O ANKI karari saklariz - motor
    parametreleri degisirse eski sinyalin gerekcesi bozulmaz."""
    setup = {"trend_pullback": "Trend icinde geri cekilme alimi",
             "breakout_retest": "Kirilim sonrasi geri test"}.get(
        getattr(d.setup_type, "value", ""), "Setup")
    parts = [setup]
    reg = getattr(getattr(d, "market_regime", None), "value", None)
    if reg:
        parts.append(f"piyasa rejimi {reg}")
    if d.rr:
        parts.append(f"risk/odul {d.rr:.1f}x")
    conf = getattr(getattr(d, "confidence", None), "value", None)
    if conf:
        parts.append(f"guven {conf}")
    for attr in ("confluence", "confluences"):
        extra = [str(c) for c in (getattr(d, attr, None) or []) if c][:3]
        if extra:
            parts.append("ek: " + ", ".join(extra))
            break
    for attr in ("volume_note", "setup_note", "note"):
        note = getattr(d, attr, None)
        if note:
            parts.append(str(note))
            break
    return " · ".join(parts)[:400]


def _cluster_id(d) -> str:
    """Kume kimligi: yon + islem gunu. Ayni gun ayni yonde dogan sinyaller
    tek kumedir (bagimsiz orneklem sayimi + kume tavani icin)."""
    return f"{d.direction.value}-{(d.timestamp_utc or '')[:10]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class SignalTracker:
    def __init__(self, db: Database, mtf_interval: str = "1h",
                 fill_window_bars: int = 14, max_track_bars: int = 28) -> None:
        self._db = db
        self._mtf = mtf_interval
        self._fill_window = fill_window_bars
        self._max_track = max_track_bars
        self._migrate()

    def _migrate(self) -> None:
        """Eski DB'lere confidence/setup_type kolonlarini guvenle ekler.
        (bybit v3.3 portu - oradaki ozyineleme hatasi burada duzeltildi.)"""
        # v3.14: fill_ts (dolum ANI - eskiden yalniz fill_price vardi,
        # "alim yapilan an" grafige isaretlenemiyordu) ve entry_reason
        # (sinyal DOGARKEN yazilan gerekce; sonradan yeniden kurulmaz).
        for col in ("confidence", "setup_type", "blocked INTEGER DEFAULT 0",
                    "block_reason", "cluster_id", "engine_sha",
                    "fill_ts INTEGER", "entry_reason", "smc_tags", "mom_pct REAL",
                    "atr_pct REAL", "atr_rank REAL"):
            try:
                ddl = col if " " in col else f"{col} TEXT"
                self._db.execute(f"ALTER TABLE signals ADD COLUMN {ddl}")
            except Exception:
                pass  # kolon zaten var
        # v4.22: dedup'un DB-seviyesi SON SAVUNMASI. maybe_track'in
        # SELECT->INSERT dizisi atomik degil; /scan ucu tick ile ayni anda
        # kosarsa (artik _scan_gate ile de engelli) ayni sembol+yonde iki
        # acik gercek kayit acilabilirdi. Kismi unique indeks bunu DB'de
        # imkansizlastirir (mevcut veri ihlalliyse olusmaz - zarar yok).
        try:
            self._db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_signals_open_unique "
                "ON signals(symbol, direction) "
                "WHERE status!='CLOSED' AND blocked=0")
        except Exception:
            pass

    # ------------------------------------------------------ veri birikimi
    def record_candles(self, series: KlineSeries) -> None:
        """Kapanmis mumlari arsivle. Son bar henuz olusuyor olabilir -> atlanir."""
        closed = series.candles[:-1]
        rows = [(series.symbol, series.interval, c.ts, c.open, c.high,
                 c.low, c.close, c.volume) for c in closed]
        self._db.executemany(
            "INSERT OR IGNORE INTO candles(symbol,interval,ts,open,high,low,close,volume) "
            "VALUES(?,?,?,?,?,?,?,?)", rows)

    def record_decision(self, d: Decision) -> None:
        self._db.execute(
            "INSERT INTO decisions(ts_utc,symbol,decision,direction,market_regime,"
            "trend_bias,setup_type,reject_reason,contract_json) VALUES(?,?,?,?,?,?,?,?,?)",
            (d.timestamp_utc, d.symbol, d.decision.value, d.direction.value,
             d.market_regime.value, d.trend_bias.value, d.setup_type.value,
             d.reject_reason, json.dumps(d.contract_dict())))

    # ------------------------------------------------------ sinyal takibi
    def maybe_track(self, d: Decision, mtf: KlineSeries,
                    mom_pct: float | None = None,
                    atr_pct: float | None = None,
                    atr_rank: float | None = None,
                    earnings_ready: bool | None = None) -> bool:
        """SIGNAL'i izlemeye al. Ayni symbol+direction icin acik GERCEK
        kayit varsa alma.

        v3.9.3 HATA DUZELTMESI: dedup sorgusu blocked satirlarini da
        "acik kayit" sayiyordu. Kill-switch GECICI bir engeldir (endeks
        gun icinde toparlanabilir): 17:00'de engellenen AAPL blocked=3
        satiri acik kalir, 19:00'da endeks duzelip ayni sinyal yeniden
        uretilirse dedup onu "zaten var" sanip IZLEMEYE ALMAZDI -
        Telegram'a sinyal gider ama golge deftere yazilmazdi (sessiz
        veri kaybi). Artik yalniz blocked=0 satirlar dedup'a girer."""
        if d.decision is not DecisionType.SIGNAL:
            return False
        existing = self._db.query_one(
            "SELECT id FROM signals WHERE symbol=? AND direction=? "
            "AND status!='CLOSED' AND blocked=0",
            (d.symbol, d.direction.value))
        if existing:
            return False
        # v4.22 DENETIM DAMGASI: bilanco takviminin sinyal DOGARKEN hazir
        # olup olmadigi contract'a yazilir. Oz-denetimin "bilanco korumasi"
        # kontrolu eskiden "SU AN ready mi + bugun sinyal var mi" diye
        # bakiyordu; gun-ici restart sonrasi yanlis KRITIK alarm, gun sonu
        # toparlanmada ise gercek ihlali gizleme uretiyordu. Dogum ani
        # damgasi iki hatayi da kapatir.
        contract = d.contract_dict()
        if earnings_ready is not None:
            contract["earnings_ready"] = bool(earnings_ready)
        self._db.execute(
            "INSERT INTO signals(symbol,direction,created_utc,entry_candle_ts,"
            "entry_min,entry_max,stop_loss,tp1,tp2,rr,time_stop_date,"
            "contract_json,confidence,setup_type,cluster_id,engine_sha,"
            "entry_reason,smc_tags,mom_pct,atr_pct,atr_rank) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (d.symbol, d.direction.value, d.timestamp_utc, mtf.candles[-1].ts,
             d.entry_zone.min, d.entry_zone.max, d.stop_loss,
             d.targets.tp1, d.targets.tp2, d.rr, d.time_stop_date,
             json.dumps(contract),
             d.confidence.value, d.setup_type.value,
             _cluster_id(d), _ENGINE_SHA, _entry_reason(d),
             _smc(d, mtf), mom_pct, atr_pct, atr_rank))
        log.info(kv(event="shadow_track", symbol=d.symbol,
                    direction=d.direction.value))
        return True

    def track_blocked(self, d, mtf: KlineSeries, reason: str,
                      blocked_class: int = 2) -> bool:
        """Girisi engellenen SIGNAL -> blocked kohortu (v3.9 genelleme).
        Siniflar: 2=portfoy tavani, 3=endeks kill-switch, 4=acilis
        penceresi (app.strategies.session_guard sabitleri).
        Ayni fill/TP/SL/time-stop dongusuyle izlenir ama TUM skor
        sorgulari blocked=0 filtreler; boylece her korumanin maliyeti/
        kazanci ('kacirdigimiz R' = hypo_r) SINIF BAZINDA olculur,
        karneye karismaz."""
        dup = self._db.query_one(
            "SELECT COUNT(*) n FROM signals WHERE symbol=? AND direction=? "
            "AND status!='CLOSED' AND blocked=?",
            (d.symbol, d.direction.value, blocked_class))
        if dup and dup["n"]:
            return False
        # v3.9.3: ayni sembol+yonde GERCEK (blocked=0) acik sinyal varsa
        # varsayimsal kohort satiri acma - ayni pozisyon hem karnede hem
        # hypo_r'da sayilirdi (cift sayim).
        real = self._db.query_one(
            "SELECT COUNT(*) n FROM signals WHERE symbol=? AND direction=? "
            "AND status!='CLOSED' AND blocked=0",
            (d.symbol, d.direction.value))
        if real and real["n"]:
            return False
        self._db.execute(
            "INSERT INTO signals(symbol,direction,created_utc,entry_candle_ts,"
            "entry_min,entry_max,stop_loss,tp1,tp2,rr,time_stop_date,"
            "confidence,setup_type,blocked,block_reason,cluster_id,engine_sha,"
            "entry_reason,smc_tags) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (d.symbol, d.direction.value, d.timestamp_utc, mtf.candles[-1].ts,
             d.entry_zone.min, d.entry_zone.max, d.stop_loss,
             d.targets.tp1, d.targets.tp2, d.rr, d.time_stop_date,
             d.confidence.value, d.setup_type.value, blocked_class, reason,
             _cluster_id(d), _ENGINE_SHA, _entry_reason(d),
             _smc(d, mtf)))
        log.info(kv(event="blocked_tracked", symbol=d.symbol,
                    blocked_class=blocked_class, reason=reason))
        return True

    def track_portfolio_blocked(self, d, mtf: KlineSeries,
                                reason: str) -> bool:
        """Geriye uyum sarmali: portfoy tavani = blocked=2."""
        return self.track_blocked(d, mtf, reason, blocked_class=2)

    # ------------------------------------------ net-R (muhafazakar muhasebe)
    FEE_USD = 1.50
    SLIP_BPS = 5.0
    REF_ACCOUNT = 10000.0
    REF_RISK_PCT = 1.0

    def cost_r(self, row: dict) -> float | None:
        """Islem maliyeti R cinsinden, referans boyutla (10k$, %1 risk).
        Midas ucreti SABIT (1.50$ x2) oldugu icin maliyet pozisyon
        buyuklugune baglidir - bybit'teki %'lik modelden temel fark."""
        entry = row.get("fill_price") or (
            ((row.get("entry_min") or 0) + (row.get("entry_max") or 0)) / 2)
        stop = row.get("stop_loss")
        if not entry or not stop:
            return None
        dist = abs(entry - stop)
        if dist <= 0:
            return None
        risk_usd = self.REF_ACCOUNT * self.REF_RISK_PCT / 100
        notional = risk_usd / dist * entry
        # kayma ARTIK cift yonlu: giris + cikis (once yalniz cikis sayiliyordu)
        cost_usd = 2 * self.FEE_USD + notional * 2 * self.SLIP_BPS / 10000
        return round(cost_usd / risk_usd, 3)

    def net_totals(self, since_utc: str | None = None) -> dict:
        """Sonuclanan islemlerde brut/net R + net beklenti.
        since_utc verilirse yalniz o andan sonra DOGAN sinyaller (kilit
        kohortu) sayilir - config-lock.md sozlesmesi."""
        q = ("SELECT entry_min,entry_max,fill_price,stop_loss,r_multiple "
             "FROM signals WHERE status='CLOSED' AND blocked=0 AND "
             "r_multiple IS NOT NULL AND outcome IN ('WIN','LOSS','EXPIRED')")
        args: tuple = ()
        if since_utc:
            q += " AND created_utc>=?"
            args = (since_utc,)
        rows = self._db.query(q, args)
        gross = net = 0.0
        for r in rows:
            gross += r["r_multiple"]
            c = self.cost_r(r) or 0.0
            net += r["r_multiple"] - c
        n = len(rows)
        return {"decided": n, "gross_r": round(gross, 2),
                "net_r": round(net, 2),
                "net_expectancy": round(net / n, 3) if n else None}

    def cluster_stats(self, since_utc: str | None = None) -> dict:
        """Sonuclanan islemlerin KUME dagilimi (2 Agu konsey karari).
        Sinyaller ayni gun+yonde kumeler halinde dogdugu icin ham islem
        sayisi istatistiksel bagimsizligi abartir; go-live kriteri artik
        kume sayisini ve en buyuk kumenin payini da sart kosuyor."""
        q = ("SELECT cluster_id, COUNT(*) n FROM signals WHERE status='CLOSED' "
             "AND blocked=0 AND r_multiple IS NOT NULL "
             "AND outcome IN ('WIN','LOSS','EXPIRED')")
        args: tuple = ()
        if since_utc:
            q += " AND created_utc>=?"
            args = (since_utc,)
        rows = self._db.query(q + " GROUP BY cluster_id", args)
        counts = [r["n"] for r in rows if r["n"]]
        total = sum(counts)
        return {"clusters": len(counts), "decided": total,
                "max_cluster_share": (round(max(counts) / total, 3)
                                      if total else None)}

    def phase_breakdown(self, since_utc: str | None = None) -> list[dict]:
        """Sonuclanan islemlerin SEANS FAZINA gore dokumu (2 Agu ozelligi).

        'Acilisin ilk yarim saatinde dogan sinyaller daha mi iyi?' sorusunu
        VERIYLE cevaplamak icin. Faz, sinyal uretilirken contract_json'a
        yazilir (yeni kolon gerekmez); eski sinyallerde alan yoksa
        'BILINMIYOR' altinda toplanir."""
        q = ("SELECT contract_json, r_multiple, entry_min, entry_max, "
             "fill_price, stop_loss FROM signals WHERE status='CLOSED' "
             "AND blocked=0 AND r_multiple IS NOT NULL "
             "AND outcome IN ('WIN','LOSS','EXPIRED')")
        args: tuple = ()
        if since_utc:
            q += " AND created_utc>=?"
            args = (since_utc,)
        buckets: dict[str, dict] = {}
        for row in self._db.query(q, args):
            phase = "BILINMIYOR"
            cj = row.get("contract_json")
            if cj:
                try:
                    phase = (json.loads(cj) or {}).get("session_phase") or phase
                except (TypeError, ValueError):
                    pass
            b = buckets.setdefault(phase, {"phase": phase, "n": 0, "wins": 0,
                                           "gross_r": 0.0, "net_r": 0.0})
            r = row["r_multiple"]
            b["n"] += 1
            b["wins"] += 1 if r > 0 else 0
            b["gross_r"] += r
            b["net_r"] += r - (self.cost_r(row) or 0.0)
        out = []
        for b in buckets.values():
            n = b["n"]
            out.append({**b,
                        "gross_r": round(b["gross_r"], 2),
                        "net_r": round(b["net_r"], 2),
                        "net_expectancy": round(b["net_r"] / n, 3) if n else None,
                        "win_rate": round(b["wins"] / n, 3) if n else None})
        return sorted(out, key=lambda x: -x["n"])

    def blocked_summary(self) -> dict:
        rows = self._db.query(
            "SELECT COUNT(*) n, SUM(CASE WHEN status='CLOSED' AND outcome "
            "IN ('WIN','LOSS','EXPIRED') THEN r_multiple ELSE 0 END) hypo_r, "
            "SUM(CASE WHEN status!='CLOSED' THEN 1 ELSE 0 END) open_n "
            "FROM signals WHERE blocked!=0")
        r = rows[0] if rows else {}
        out = {"total": r.get("n") or 0, "open": r.get("open_n") or 0,
               "hypo_r": round(r.get("hypo_r") or 0.0, 2)}
        # v3.9: sinif bazinda kirilim - hangi koruma ne kadar R
        # engelledi/kacirdi ayri ayri olculebilsin (2=tavan,
        # 3=kill-switch, 4=acilis penceresi)
        by_cls = self._db.query(
            "SELECT blocked, COUNT(*) n, SUM(CASE WHEN status='CLOSED' AND "
            "outcome IN ('WIN','LOSS','EXPIRED') THEN r_multiple ELSE 0 END) "
            "hypo_r FROM signals WHERE blocked!=0 GROUP BY blocked")
        out["by_class"] = {
            str(int(row["blocked"])): {
                "n": row["n"], "hypo_r": round(row.get("hypo_r") or 0.0, 2)}
            for row in by_cls}
        return out

    def evaluate_open(self, symbol: str) -> None:
        """Acik sinyalleri arsivlenen 1h mumlarla degerlendir."""
        open_signals = self._db.query(
            "SELECT * FROM signals WHERE symbol=? AND status!='CLOSED'", (symbol,))
        for sig in open_signals:
            candles = self._db.query(
                "SELECT * FROM candles WHERE symbol=? AND interval=? AND ts>? "
                "ORDER BY ts ASC", (symbol, self._mtf, sig["entry_candle_ts"]))
            if candles:
                self._evaluate_signal(sig, candles)

    def _evaluate_signal(self, sig: dict, candles: list[dict]) -> None:
        is_long = sig["direction"] == Direction.LONG.value
        fill_price = sig["fill_price"]
        filled_at_idx: int | None = None
        # v4.22 TIME-STOP CAPASI: dolum onceki turda/restart oncesinde
        # kaydedildiyse filled_at_idx bellekte YOKTU ve bars_held sinyal
        # DOGUMUNDAN sayiliyordu -> time-stop 14 bara kadar erken ve
        # degerlendirme turu sayisina bagli (non-determinist). fill_ts
        # v3.14'ten beri DB'de duruyordu ama hic okunmuyordu.
        if fill_price is not None and sig.get("fill_ts"):
            for j, cc in enumerate(candles):
                if cc["ts"] >= sig["fill_ts"]:
                    filled_at_idx = j
                    break

        for i, c in enumerate(candles):
            just_filled = False
            # --- 1) fill kontrolu ---
            if fill_price is None:
                # 2 Agu duzeltmesi (konsey 5/5: "%100 dolum iyimserligi"):
                # Bolgenin yakin ucuna BIR TICK dokunmak dolum saymaz.
                # Emirler MANUEL giriliyor (Telegram -> Midas, 30-60 sn
                # gecikme); fiyatin bolgeyi TAMAMEN katetmis olmasini sart
                # kosuyoruz. Bu muhafazakar bir ALT SINIR - gercek dolum
                # oraninin altinda kalabilir, ama iyimser tarafta hata
                # yapmaktansa kotumser tarafta hata yapmayi tercih ediyoruz.
                touched = (c["low"] <= sig["entry_min"] if is_long
                           else c["high"] >= sig["entry_max"])
                if touched:
                    fill_price = sig["entry_max"] if is_long else sig["entry_min"]
                    # gap ile bolgenin OTESINDE acilis: daha iyi fiyattan dolum
                    if is_long and c["open"] < sig["entry_min"]:
                        fill_price = c["open"]
                    elif not is_long and c["open"] > sig["entry_max"]:
                        fill_price = c["open"]
                    filled_at_idx = i
                    # v3.14: dolum ANI da kaydedilir (grafikteki "alim
                    # yapilan an" isareti bunu kullanir)
                    self._db.execute(
                        "UPDATE signals SET status='FILLED', fill_price=?, "
                        "fill_ts=? WHERE id=?",
                        (fill_price, c["ts"], sig["id"]))
                elif i + 1 >= self._fill_window:
                    self._close(sig["id"], "NOT_FILLED", None, 0.0)
                    return
                else:
                    continue
                # v4.22 DOLUM BARI: eski kod burada 'continue' ediyordu -
                # bolgeyi katedip AYNI barda stop'u da kesen mum zarar
                # YAZMIYORDU (iyimser hata; derin katetme tam da riskli
                # dolumdur). Artik dolum barinda da sonuc kontrolune
                # dusulur; just_filled bayragi asagida kotumser kurallari
                # secer (gap dallari kapali - acilis dolumdan ONCEYDI).
                just_filled = True

            # --- 2) sonuc kontrolu (gap muhasebeli) ---
            risk = ((fill_price - sig["stop_loss"]) if is_long
                    else (sig["stop_loss"] - fill_price))
            if risk <= 0:
                # gap ile bolge+stop OTESINDE acilis: dolum=acilis oldugundan
                # fiili P&L ~0; plan riski tanimsiz -> AMBIGUOUS (0R) kalir.
                self._close(sig["id"], "AMBIGUOUS", fill_price, 0.0)
                return
            hit_stop = (c["low"] <= sig["stop_loss"] if is_long
                        else c["high"] >= sig["stop_loss"])
            hit_tp = (c["high"] >= sig["tp1"] if is_long
                      else c["low"] <= sig["tp1"])
            gap_stop = (not just_filled
                        and (c["open"] < sig["stop_loss"] if is_long
                             else c["open"] > sig["stop_loss"]))
            gap_tp = (not just_filled
                      and (c["open"] > sig["tp1"] if is_long
                           else c["open"] < sig["tp1"]))
            if just_filled:
                # Dolum barinda TP'nin dolumdan once mi kesildigi bilinemez:
                # stop+TP -> AMBIGUOUS; yalniz stop -> LOSS (bolge stop
                # yonunde katedildi, sira belli); yalniz TP -> iyimser WIN
                # YAZILMAZ, pozisyon acik kalir (kotumser muhasebe ilkesi).
                if hit_stop and hit_tp:
                    self._close(sig["id"], "AMBIGUOUS", fill_price, 0.0)
                    return
                if hit_stop:
                    exit_price = sig["stop_loss"]
                    pnl = ((exit_price - fill_price) if is_long
                           else (fill_price - exit_price))
                    self._close(sig["id"], "LOSS", exit_price,
                                round(pnl / risk, 2))
                    return
            elif gap_stop:
                # v4.22 GAP SIRASI: acilis stop OTESINDEYSE sira BILINIR
                # (once acilis geldi, pozisyon orada kapandi) - bar icinde
                # TP de kesilse sonuc LOSS@acilis'tir. Eski kod stop+TP'yi
                # gap'ten ONCE kontrol edip AMBIGUOUS(0R) yaziyor, en kotu
                # gap zararlarini defterden dusuruyordu (yazili kural:
                # "gap'te ACILIS fiyatindan cikis").
                exit_price = c["open"]
                pnl = ((exit_price - fill_price) if is_long
                       else (fill_price - exit_price))
                self._close(sig["id"], "LOSS", exit_price, round(pnl / risk, 2))
                return
            elif gap_tp:
                # simetrik: acilis hedef otesindeyse WIN@acilis (lehte gap).
                exit_price = c["open"]
                reward = ((exit_price - fill_price) if is_long
                          else (fill_price - exit_price))
                self._close(sig["id"], "WIN", exit_price,
                            round(reward / risk, 2))
                return
            elif hit_stop and hit_tp:
                self._close(sig["id"], "AMBIGUOUS", fill_price, 0.0)
                return
            elif hit_stop:
                pnl = ((sig["stop_loss"] - fill_price) if is_long
                       else (fill_price - sig["stop_loss"]))
                self._close(sig["id"], "LOSS", sig["stop_loss"],
                            round(pnl / risk, 2))
                return
            elif hit_tp:
                reward = ((sig["tp1"] - fill_price) if is_long
                          else (fill_price - sig["tp1"]))
                self._close(sig["id"], "WIN", sig["tp1"],
                            round(reward / risk, 2))
                return
            bars_held = i - (filled_at_idx if filled_at_idx is not None else 0)
            if bars_held >= self._max_track:
                pnl = (c["close"] - fill_price) if is_long else (fill_price - c["close"])
                self._close(sig["id"], "EXPIRED", c["close"], round(pnl / risk, 2))
                return

    def _close(self, signal_id: int, outcome: str,
               exit_price: float | None, r_multiple: float) -> None:
        self._db.execute(
            "UPDATE signals SET status='CLOSED', outcome=?, exit_price=?, "
            "r_multiple=?, closed_utc=? WHERE id=?",
            (outcome, exit_price, r_multiple, _now_iso(), signal_id))
        log.info(kv(event="shadow_close", signal_id=signal_id,
                    outcome=outcome, r=r_multiple))

    # ------------------------------------------------------- istatistik
    def stats(self) -> dict:
        by_outcome = {r["outcome"]: {"count": r["n"], "sum_r": r["sum_r"] or 0.0}
                      for r in self._db.query(
                          "SELECT outcome, COUNT(*) n, SUM(r_multiple) sum_r "
                          "FROM signals WHERE status='CLOSED' AND blocked=0 "
                          "GROUP BY outcome")}
        wins = by_outcome.get("WIN", {}).get("count", 0)
        losses = by_outcome.get("LOSS", {}).get("count", 0)
        decided = wins + losses
        total_r = round(sum(v["sum_r"] for v in by_outcome.values()), 2)
        open_row = self._db.query_one(
            "SELECT COUNT(*) n FROM signals WHERE status!='CLOSED' AND blocked=0")
        per_symbol = self._db.query(
            "SELECT symbol, outcome, COUNT(*) n, ROUND(SUM(r_multiple),2) sum_r "
            "FROM signals WHERE status='CLOSED' AND blocked=0 "
            "GROUP BY symbol, outcome ORDER BY symbol")
        by_direction = self._db.query(
            "SELECT direction, outcome, COUNT(*) n, ROUND(SUM(r_multiple),2) sum_r "
            "FROM signals WHERE status='CLOSED' AND blocked=0 "
            "GROUP BY direction, outcome")
        counts = self._db.query_one(
            "SELECT (SELECT COUNT(*) FROM decisions) d, (SELECT COUNT(*) FROM candles) c")
        return {
            "note": ("Shadow accounting: conservative fills (full zone "
                     "traversal), gap-aware exits. Costs ARE modelled: "
                     "2x$1.50 fixed fee + 5bp two-way slippage at $10k/1% "
                     "reference size -> see r_net / net_totals(). "
                     "r_multiple below is GROSS. Not real trading results."),
            "open_signals": open_row["n"] if open_row else 0,
            "closed_by_outcome": by_outcome,
            "win_rate": round(wins / decided, 3) if decided else None,
            "decided_trades": decided,
            "total_r_multiple": total_r,
            "per_symbol": per_symbol,
            "by_direction": by_direction,
            "dataset": {"decisions_recorded": counts["d"],
                        "candles_archived": counts["c"]},
        }

    def recent_signals(self, limit: int = 50) -> list[dict]:
        rows = self._db.query(
            "SELECT id,symbol,direction,created_utc,entry_candle_ts,status,outcome,"
            "entry_min,entry_max,stop_loss,tp1,tp2,rr,time_stop_date,fill_price,"
            "exit_price,r_multiple,closed_utc,confidence,setup_type,contract_json,"
            "fill_ts,entry_reason,smc_tags,mom_pct,atr_pct,atr_rank "
            "FROM signals WHERE blocked=0 ORDER BY id DESC LIMIT ?",
            (limit,))
        for r in rows:                       # net-R (referans boy) rapora
            if r.get("r_multiple") is not None:
                c = self.cost_r(r)
                if c is not None:
                    r["cost_r"] = c
                    r["r_net"] = round(r["r_multiple"] - c, 2)
            # Giris kaniti (2 Agu ozelligi): kurulum seviyesi + hacim notu +
            # confluence + gecersiz kilinma kosulu - contract_json'dan cozulur
            # (yeni kolon acmadan; eski sinyallerde bu alan yoksa sessizce atlanir)
            cj = r.pop("contract_json", None)
            if cj:
                try:
                    payload = json.loads(cj)
                except (TypeError, ValueError):
                    payload = {}
                if payload.get("setup_level") is not None:
                    r["setup_level"] = payload["setup_level"]
                if payload.get("volume_note"):
                    r["volume_note"] = payload["volume_note"]
                if payload.get("confluence"):
                    r["confluence"] = payload["confluence"]
                if payload.get("invalidation"):
                    r["invalidation"] = payload["invalidation"]
        return rows

    def export_signals(self, limit: int = 500) -> list[dict]:
        """Gercek (blocked=0) satirlarin HAM dokumu - gist yedegi icin
        (v4.22). recent_signals() bir RAPORDUR: cluster_id/engine_sha
        secilmiyor, contract_json parcalanip atiliyor. Yedek o dosyadan
        beslenince her restart kume kimligini siliyordu -> cluster_stats
        tum tarihi TEK NULL kumede topluyor, go-live'in '25 kume / tek
        kume <=%25' kriterleri ve mom_pct/atr dilim analizi bozuluyordu
        (v4.21'in gercek-satir ayagi)."""
        return self._db.query(
            "SELECT symbol,direction,created_utc,entry_candle_ts,entry_min,"
            "entry_max,stop_loss,tp1,tp2,rr,time_stop_date,status,outcome,"
            "fill_price,exit_price,r_multiple,closed_utc,confidence,"
            "setup_type,cluster_id,engine_sha,fill_ts,entry_reason,smc_tags,"
            "mom_pct,atr_pct,atr_rank,contract_json "
            "FROM signals WHERE blocked=0 ORDER BY id DESC LIMIT ?", (limit,))

    def recent_signals_blocked(self, limit: int = 500) -> list[dict]:
        """Blocked kohort satirlari - gist yedegi icin (v4.21, 7 Agu vakasi).
        recent_signals() blocked=0 filtreler (karne icin DOGRU) ama yedek de
        ayni dosyayi kullaninca her restart blocked kohortlarini (tavan/
        kill-switch/acilis/hipotez) sessizce siliyordu; 'kacirdigimiz R'
        olcumu v3.9'dan beri hic birikememisti. Ham satir dondurur
        (cost_r/contract susu yok - bu bir rapor degil yedek)."""
        return self._db.query(
            "SELECT symbol,direction,created_utc,entry_candle_ts,entry_min,"
            "entry_max,stop_loss,tp1,tp2,rr,time_stop_date,status,outcome,"
            "fill_price,exit_price,r_multiple,closed_utc,confidence,setup_type,"
            "blocked,block_reason,cluster_id,engine_sha,fill_ts,entry_reason "
            "FROM signals WHERE blocked!=0 ORDER BY id DESC LIMIT ?", (limit,))

    def recent_decisions(self, limit: int = 2000) -> list[dict]:
        return self._db.query(
            "SELECT ts_utc,symbol,decision,direction,market_regime,trend_bias,"
            "setup_type,reject_reason FROM decisions ORDER BY id DESC LIMIT ?",
            (limit,))

    def export_candles(self, symbol: str, interval: str) -> list[dict]:
        return self._db.query(
            "SELECT ts,open,high,low,close,volume FROM candles "
            "WHERE symbol=? AND interval=? ORDER BY ts ASC", (symbol, interval))

    def open_count_by(self, direction: str) -> int:
        rows = self._db.query(
            "SELECT COUNT(*) AS n FROM signals WHERE status!='CLOSED' "
            "AND blocked=0 AND direction=?", (direction,))
        return int(rows[0]["n"]) if rows else 0

    def open_count_cluster(self, cluster_id: str) -> int:
        rows = self._db.query(
            "SELECT COUNT(*) AS n FROM signals WHERE status!='CLOSED' "
            "AND blocked=0 AND cluster_id=?", (cluster_id,))
        return int(rows[0]["n"]) if rows else 0

    def open_count(self) -> int:
        rows = self._db.query(
            "SELECT COUNT(*) AS n FROM signals WHERE status!='CLOSED' AND blocked=0")
        return int(rows[0]["n"]) if rows else 0

    def max_drawdown_r(self, since_utc: str | None = None) -> float:
        """Kapanis sirasiyla kumulatif NET-R egrisinin en derin dususu (R).

        v4.22: egri BRUT r_multiple'dan hesaplaniyordu; go-live'in diger
        bacagi (beklenti) NET iken DD brut kaliyordu. Net egri her islemde
        maliyet kadar asagida -> net DD daima daha derin; 15-20 islemlik
        seride fark 1-2.5R. Brut 7.5R gosterirken net >8R olabilir ve
        go-live yanlis GECER / 8R freni gec tetiklenirdi."""
        q = ("SELECT r_multiple,fill_price,entry_min,entry_max,stop_loss "
             "FROM signals WHERE status='CLOSED' AND blocked=0 "
             "AND r_multiple IS NOT NULL AND outcome NOT IN "
             "('NOT_FILLED','AMBIGUOUS')")
        args: tuple = ()
        if since_utc:
            q += " AND created_utc>=?"
            args = (since_utc,)
        rows = self._db.query(q + " ORDER BY closed_utc", args)
        cum = peak = dd = 0.0
        for r in rows:
            cum += r["r_multiple"] - (self.cost_r(r) or 0.0)
            peak = max(peak, cum)
            dd = max(dd, peak - cum)
        return round(dd, 2)

    def first_signal_utc(self) -> str | None:
        rows = self._db.query("SELECT MIN(created_utc) AS m FROM signals WHERE blocked=0")
        return rows[0]["m"] if rows and rows[0]["m"] else None

    def fill_quality(self) -> dict | None:
        """FILLED sinyallerin dolum kalitesi: girisden bu yana MFE/MAE (R).
        MFE = lehte en iyi hareket, MAE = aleyhte en derin hareket. Konsey
        onerisi: 'giris bolgesi kovaliyor mu' sorusunun olcusu."""
        rows = self._db.query(
            "SELECT symbol,direction,entry_candle_ts,fill_price,stop_loss "
            "FROM signals WHERE status='FILLED' AND blocked=0 "
            "AND fill_price IS NOT NULL")
        if not rows:
            return None
        per = []
        for r in rows:
            cs = self._db.query(
                "SELECT high,low FROM candles WHERE symbol=? AND interval=? "
                "AND ts>?", (r["symbol"], self._mtf, r["entry_candle_ts"]))
            if not cs:
                continue
            risk = abs(r["fill_price"] - r["stop_loss"]) or 1e-9
            sign = 1 if r["direction"] == "LONG" else -1
            mfe = max(sign * (c["high" if sign > 0 else "low"] - r["fill_price"])
                      for c in cs) / risk
            mae = min(sign * (c["low" if sign > 0 else "high"] - r["fill_price"])
                      for c in cs) / risk
            per.append({"symbol": r["symbol"], "mfe_r": round(mfe, 2),
                        "mae_r": round(mae, 2)})
        if not per:
            return None
        mid = len(per) // 2
        med = lambda k: sorted(p[k] for p in per)[mid]
        worst = min(per, key=lambda p: p["mae_r"])
        return {"n": len(per), "mfe_median": med("mfe_r"),
                "mae_median": med("mae_r"),
                "worst": f'{worst["symbol"]} {worst["mae_r"]:+.2f}R', "per": per}

    def setup_mix(self) -> dict:
        """Acik sinyallerde setup/guven dagilimi (denge izlemesi)."""
        rows = self._db.query(
            # v3.21: blocked=0 filtresi eklendi - blocked kohortlari (ozellikle
            # yeni hacim/pullback hipotezi, sinif 5) denge panelinde PB sayisini
            # sisirip "mix duzeldi" yanilsamasi yaratirdi. Panel CANLI defteri
            # yansitir; hipotez kohortu blocked_summary'de ayri okunur.
            "SELECT setup_type, confidence, COUNT(*) AS n FROM signals "
            "WHERE status!='CLOSED' AND blocked=0 GROUP BY setup_type, confidence")
        mix: dict = {"setup": {}, "confidence": {}}
        for r in rows:
            st = (r["setup_type"] or "?").replace("breakout_retest", "BO")                                          .replace("trend_pullback", "PB")
            mix["setup"][st] = mix["setup"].get(st, 0) + r["n"]
            cf = r["confidence"] or "?"
            mix["confidence"][cf] = mix["confidence"].get(cf, 0) + r["n"]
        return mix

    def open_symbols(self) -> list[str]:
        """Acik (PENDING/FILLED) sinyali olan semboller - orphan eval icin."""
        rows = self._db.query(
            "SELECT DISTINCT symbol FROM signals WHERE status!='CLOSED'")  # blocked dahil: yasamalilar
        return [r["symbol"] for r in rows]

    def archive_symbols(self, retention_days: int = 30) -> list[str]:
        """Mum arsivine girecek semboller: acik sinyali olan VEYA son
        retention_days icinde kapanan. (Konsey: gist sonsuza buyumesin.)"""
        cutoff = (datetime.now(timezone.utc)
                  - timedelta(days=retention_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = self._db.query(
            "SELECT DISTINCT symbol FROM signals WHERE status!='CLOSED' "
            "OR closed_utc IS NULL OR closed_utc>=?", (cutoff,))
        return [r["symbol"] for r in rows]

    def signal_symbols(self) -> list[str]:
        """Sinyal kaydi olan semboller (gist candle_mode=signals icin)."""
        return [r["symbol"] for r in
                self._db.query("SELECT DISTINCT symbol FROM signals ORDER BY symbol")]

    # ------------------------------------------- gist restore destegi
    def candles_count(self) -> int:
        row = self._db.query_one("SELECT COUNT(*) n FROM candles")
        return row["n"] if row else 0

    def import_candles(self, symbol: str, interval: str,
                       rows: list[tuple]) -> int:
        """rows: [(ts,open,high,low,close,volume), ...] - tekrarsiz eklenir."""
        self._db.executemany(
            "INSERT OR IGNORE INTO candles(symbol,interval,ts,open,high,low,close,volume) "
            "VALUES(?,?,?,?,?,?,?,?)",
            [(symbol, interval, *r) for r in rows])
        return len(rows)

    def import_signals(self, rows: list[dict]) -> int:
        """Gist yedekten sinyal kayitlarini geri yukler (created_utc ile tekrarsiz)."""
        imported = 0
        for r in rows:
            exists = self._db.query_one(
                "SELECT id FROM signals WHERE symbol=? AND direction=? AND created_utc=?",
                (r.get("symbol"), r.get("direction"), r.get("created_utc")))
            if exists:
                continue
            # v4.22: cluster_id/engine_sha/fill_ts/etiketler/contract da
            # geri yuklenir (eski yedeklerde alan yoksa None - geriye uyum).
            self._db.execute(
                "INSERT INTO signals(symbol,direction,created_utc,entry_candle_ts,"
                "entry_min,entry_max,stop_loss,tp1,tp2,rr,time_stop_date,status,"
                "outcome,fill_price,exit_price,r_multiple,closed_utc,"
                "confidence,setup_type,cluster_id,engine_sha,fill_ts,"
                "entry_reason,smc_tags,mom_pct,atr_pct,atr_rank,contract_json) "
                "VALUES(" + ",".join("?" * 28) + ")",
                (r.get("symbol"), r.get("direction"), r.get("created_utc"),
                 r.get("entry_candle_ts"), r.get("entry_min"), r.get("entry_max"),
                 r.get("stop_loss"), r.get("tp1"), r.get("tp2"), r.get("rr"),
                 r.get("time_stop_date"), r.get("status", "PENDING"),
                 r.get("outcome"), r.get("fill_price"), r.get("exit_price"),
                 r.get("r_multiple"), r.get("closed_utc"),
                 r.get("confidence"), r.get("setup_type"),
                 r.get("cluster_id"), r.get("engine_sha"), r.get("fill_ts"),
                 r.get("entry_reason"), r.get("smc_tags"), r.get("mom_pct"),
                 r.get("atr_pct"), r.get("atr_rank"), r.get("contract_json")))
            imported += 1
        return imported

    def import_signals_blocked(self, rows: list[dict]) -> int:
        """Blocked kohort satirlarini yedekten geri yukler (v4.21).
        AYRI yol cunku: (1) import_signals'in uclu dedup anahtari
        (symbol+direction+created_utc) blocked sinifini bilmez - ayni
        sembol/yon/an hem gercek hem varsayimsal satir tasiyabilir;
        anahtara blocked SINIFI eklenir. (2) blocked/block_reason/
        cluster_id/engine_sha kolonlari da tasinmali - 'kacirdigimiz R'
        analizi sinif ve kume kimligi olmadan yapilamaz."""
        imported = 0
        for r in rows:
            blk = r.get("blocked") or 0
            if not blk:
                continue                    # gercek satir bu yoldan girmez
            exists = self._db.query_one(
                "SELECT id FROM signals WHERE symbol=? AND direction=? "
                "AND created_utc=? AND blocked=?",
                (r.get("symbol"), r.get("direction"), r.get("created_utc"), blk))
            if exists:
                continue
            self._db.execute(
                "INSERT INTO signals(symbol,direction,created_utc,"
                "entry_candle_ts,entry_min,entry_max,stop_loss,tp1,tp2,rr,"
                "time_stop_date,status,outcome,fill_price,exit_price,"
                "r_multiple,closed_utc,confidence,setup_type,blocked,"
                "block_reason,cluster_id,engine_sha,fill_ts,entry_reason) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (r.get("symbol"), r.get("direction"), r.get("created_utc"),
                 r.get("entry_candle_ts"), r.get("entry_min"),
                 r.get("entry_max"), r.get("stop_loss"), r.get("tp1"),
                 r.get("tp2"), r.get("rr"), r.get("time_stop_date"),
                 r.get("status", "PENDING"), r.get("outcome"),
                 r.get("fill_price"), r.get("exit_price"),
                 r.get("r_multiple"), r.get("closed_utc"),
                 r.get("confidence"), r.get("setup_type"), blk,
                 r.get("block_reason"), r.get("cluster_id"),
                 r.get("engine_sha"), r.get("fill_ts"),
                 r.get("entry_reason")))
            imported += 1
        return imported
