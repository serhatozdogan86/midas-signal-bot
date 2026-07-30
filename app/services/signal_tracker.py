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
        for col in ("confidence", "setup_type", "blocked INTEGER DEFAULT 0",
                    "block_reason", "cluster_id", "engine_sha"):
            try:
                ddl = col if " " in col else f"{col} TEXT"
                self._db.execute(f"ALTER TABLE signals ADD COLUMN {ddl}")
            except Exception:
                pass  # kolon zaten var

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
    def maybe_track(self, d: Decision, mtf: KlineSeries) -> bool:
        """SIGNAL'i izlemeye al. Ayni symbol+direction icin acik kayit varsa alma."""
        if d.decision is not DecisionType.SIGNAL:
            return False
        existing = self._db.query_one(
            "SELECT id FROM signals WHERE symbol=? AND direction=? AND status!='CLOSED'",
            (d.symbol, d.direction.value))
        if existing:
            return False
        self._db.execute(
            "INSERT INTO signals(symbol,direction,created_utc,entry_candle_ts,"
            "entry_min,entry_max,stop_loss,tp1,tp2,rr,time_stop_date,"
            "contract_json,confidence,setup_type,cluster_id,engine_sha) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (d.symbol, d.direction.value, d.timestamp_utc, mtf.candles[-1].ts,
             d.entry_zone.min, d.entry_zone.max, d.stop_loss,
             d.targets.tp1, d.targets.tp2, d.rr, d.time_stop_date,
             json.dumps(d.contract_dict()),
             d.confidence.value, d.setup_type.value,
             _cluster_id(d), _ENGINE_SHA))
        log.info(kv(event="shadow_track", symbol=d.symbol,
                    direction=d.direction.value))
        return True

    def track_portfolio_blocked(self, d, mtf: KlineSeries,
                                reason: str) -> bool:
        """Portfoy tavanina takilan SIGNAL -> blocked=2 kohortu.
        Ayni fill/TP/SL/time-stop dongusuyle izlenir ama TUM skor
        sorgulari blocked=0 filtreler; boylece tavanin maliyeti
        ('kacirdigimiz R') olculur, karneye karismaz."""
        dup = self._db.query_one(
            "SELECT COUNT(*) n FROM signals WHERE symbol=? AND direction=? "
            "AND status!='CLOSED' AND blocked=2", (d.symbol, d.direction.value))
        if dup and dup["n"]:
            return False
        self._db.execute(
            "INSERT INTO signals(symbol,direction,created_utc,entry_candle_ts,"
            "entry_min,entry_max,stop_loss,tp1,tp2,rr,time_stop_date,"
            "confidence,setup_type,blocked,block_reason,cluster_id,engine_sha) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,2,?,?,?)",
            (d.symbol, d.direction.value, d.timestamp_utc, mtf.candles[-1].ts,
             d.entry_zone.min, d.entry_zone.max, d.stop_loss,
             d.targets.tp1, d.targets.tp2, d.rr, d.time_stop_date,
             d.confidence.value, d.setup_type.value, reason,
             _cluster_id(d), _ENGINE_SHA))
        log.info(kv(event="portfolio_blocked_tracked", symbol=d.symbol,
                    reason=reason))
        return True

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
        cost_usd = 2 * self.FEE_USD + notional * self.SLIP_BPS / 10000
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

    def blocked_summary(self) -> dict:
        rows = self._db.query(
            "SELECT COUNT(*) n, SUM(CASE WHEN status='CLOSED' AND outcome "
            "IN ('WIN','LOSS','EXPIRED') THEN r_multiple ELSE 0 END) hypo_r, "
            "SUM(CASE WHEN status!='CLOSED' THEN 1 ELSE 0 END) open_n "
            "FROM signals WHERE blocked!=0")
        r = rows[0] if rows else {}
        return {"total": r.get("n") or 0, "open": r.get("open_n") or 0,
                "hypo_r": round(r.get("hypo_r") or 0.0, 2)}

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

        for i, c in enumerate(candles):
            # --- 1) fill kontrolu ---
            if fill_price is None:
                touched = (c["low"] <= sig["entry_max"] if is_long
                           else c["high"] >= sig["entry_min"])
                if touched:
                    fill_price = sig["entry_max"] if is_long else sig["entry_min"]
                    # gap ile bolgenin OTESINDE acilis: daha iyi fiyattan dolum
                    if is_long and c["open"] < sig["entry_min"]:
                        fill_price = c["open"]
                    elif not is_long and c["open"] > sig["entry_max"]:
                        fill_price = c["open"]
                    filled_at_idx = i
                    self._db.execute(
                        "UPDATE signals SET status='FILLED', fill_price=? WHERE id=?",
                        (fill_price, sig["id"]))
                elif i + 1 >= self._fill_window:
                    self._close(sig["id"], "NOT_FILLED", None, 0.0)
                    return
                continue

            # --- 2) sonuc kontrolu (gap muhasebeli) ---
            risk = ((fill_price - sig["stop_loss"]) if is_long
                    else (sig["stop_loss"] - fill_price))
            if risk <= 0:
                self._close(sig["id"], "AMBIGUOUS", fill_price, 0.0)
                return
            hit_stop = (c["low"] <= sig["stop_loss"] if is_long
                        else c["high"] >= sig["stop_loss"])
            hit_tp = (c["high"] >= sig["tp1"] if is_long
                      else c["low"] <= sig["tp1"])
            if hit_stop and hit_tp:
                self._close(sig["id"], "AMBIGUOUS", fill_price, 0.0)
                return
            if hit_stop:
                # Gap-through-stop: acilis stop'un otesindeyse cikis = acilis
                exit_price = sig["stop_loss"]
                if is_long and c["open"] < sig["stop_loss"]:
                    exit_price = c["open"]
                elif not is_long and c["open"] > sig["stop_loss"]:
                    exit_price = c["open"]
                pnl = (exit_price - fill_price) if is_long else (fill_price - exit_price)
                self._close(sig["id"], "LOSS", exit_price, round(pnl / risk, 2))
                return
            if hit_tp:
                # Gap-through-TP: acilis hedefin otesindeyse cikis = acilis (lehte)
                exit_price = sig["tp1"]
                if is_long and c["open"] > sig["tp1"]:
                    exit_price = c["open"]
                elif not is_long and c["open"] < sig["tp1"]:
                    exit_price = c["open"]
                reward = (exit_price - fill_price) if is_long else (fill_price - exit_price)
                self._close(sig["id"], "WIN", exit_price, round(reward / risk, 2))
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
            "note": ("Shadow accounting: estimated fills, gap-aware exits, "
                     "no commissions/slippage. Not real trading results."),
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
            "exit_price,r_multiple,closed_utc,confidence,setup_type "
            "FROM signals WHERE blocked=0 ORDER BY id DESC LIMIT ?",
            (limit,))
        for r in rows:                       # net-R (referans boy) rapora
            if r.get("r_multiple") is not None:
                c = self.cost_r(r)
                if c is not None:
                    r["cost_r"] = c
                    r["r_net"] = round(r["r_multiple"] - c, 2)
        return rows

    def recent_decisions(self, limit: int = 2000) -> list[dict]:
        return self._db.query(
            "SELECT ts_utc,symbol,decision,direction,market_regime,trend_bias,"
            "setup_type,reject_reason FROM decisions ORDER BY id DESC LIMIT ?",
            (limit,))

    def export_candles(self, symbol: str, interval: str) -> list[dict]:
        return self._db.query(
            "SELECT ts,open,high,low,close,volume FROM candles "
            "WHERE symbol=? AND interval=? ORDER BY ts ASC", (symbol, interval))

    def open_count(self) -> int:
        rows = self._db.query(
            "SELECT COUNT(*) AS n FROM signals WHERE status!='CLOSED' AND blocked=0")
        return int(rows[0]["n"]) if rows else 0

    def max_drawdown_r(self, since_utc: str | None = None) -> float:
        """Kapanis sirasiyla kumulatif R egrisinin en derin dususu (R)."""
        q = ("SELECT r_multiple FROM signals WHERE status='CLOSED' AND blocked=0 "
             "AND r_multiple IS NOT NULL AND outcome NOT IN "
             "('NOT_FILLED','AMBIGUOUS')")
        args: tuple = ()
        if since_utc:
            q += " AND created_utc>=?"
            args = (since_utc,)
        rows = self._db.query(q + " ORDER BY closed_utc", args)
        cum = peak = dd = 0.0
        for r in rows:
            cum += r["r_multiple"]
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
            "SELECT setup_type, confidence, COUNT(*) AS n FROM signals "
            "WHERE status!='CLOSED' GROUP BY setup_type, confidence")
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
            self._db.execute(
                "INSERT INTO signals(symbol,direction,created_utc,entry_candle_ts,"
                "entry_min,entry_max,stop_loss,tp1,tp2,rr,time_stop_date,status,"
                "outcome,fill_price,exit_price,r_multiple,closed_utc,"
                "confidence,setup_type) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (r.get("symbol"), r.get("direction"), r.get("created_utc"),
                 r.get("entry_candle_ts"), r.get("entry_min"), r.get("entry_max"),
                 r.get("stop_loss"), r.get("tp1"), r.get("tp2"), r.get("rr"),
                 r.get("time_stop_date"), r.get("status", "PENDING"),
                 r.get("outcome"), r.get("fill_price"), r.get("exit_price"),
                 r.get("r_multiple"), r.get("closed_utc"),
                 r.get("confidence"), r.get("setup_type")))
            imported += 1
        return imported
