"""
CIKIS LABORATUVARI (v3.19) - ayni sinyale paralel cikis politikalari.

AMAC: Backtest bulgusunu ("sorun giriste degil cikista: TP1'de tam
cikis + 4 gun time-stop, alti stratejiyi de negatife cekiyor; ayni
girisler genis stop + hedefsiz + uzun tutmayla pozitif") KENDI CANLI
sinyallerimizle dogrulamak. Kilit kohortu (V0 = canli defter) HIC
DEGISMEZ; varyantlar ayni sinyallerin ayni mum arsivi uzerinde SANAL
yeniden oynatimidir.

KURAL BIREBIRLIGI: dolum, gap ve ayni-bar kotumserligi canli
SignalTracker._evaluate_signal ile AYNI (bkz. test_v0_mirrors_live):
- dolum: bolgenin TAMAMEN katedilmesi sart (LONG: low<=entry_min),
  dolum fiyati kotu uc (LONG: entry_max); acilis bolge otesindeyse
  acilistan (lehte gap)
- stop gap: acilis stop otesindeyse cikis ACILISTAN
- ayni barda hem stop hem hedef -> AMBIGUOUS (0R) [hedefli varyantlarda]
- dolum penceresi ayni (fill_window bar)

VARYANTLAR (cikis disinda HICBIR sey degismez):
- V1_KISMI : sinyalin KENDI seviyeleri; TP1'de %50 cikis, kalan %50
  TP2 hedefli, stop sabit; kalan bacak icin sure 70 bar (~10 gun).
- V2_GENIS : hedef YOK; stop, sinyalin kendi riskinin 5/3'u kadar
  uzaga tasinir (1.2 ATR tabanina gore ~2.0 ATR esdegeri); sure
  140 bar (~20 gun). Backtest'in kazanan konfigurasyonu.

MALIYET: Midas modeli bacak basina uygulanir - 1.50$ / islem + 5bp
kayma x islem gorulen buyukluk. V1 dolup iki bacakla cikarsa 3 islem
(4.50$); kayma toplami tam boyutta 2 gecisle ayni. Referans 10k$/%1.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass

from app.logging_setup import kv

log = logging.getLogger("exit_lab")

REF_NOTIONAL = 10_000.0
REF_RISK = 100.0            # %1
FEE_PER_TRADE = 1.50
SLIP_PCT = 0.0005

VARIANTS: dict[str, dict] = {
    "V1_KISMI": {"mode": "partial", "tp1_frac": 0.5, "rest_max_bars": 70},
    "V2_GENIS": {"mode": "wide", "stop_mult": 5.0 / 3.0, "max_bars": 140},
    # v3.24: TARAMA BULGUSU - sabit hedefi kaldirmak, stopu genisletmekten
    # ve sureyi uzatmaktan DAHA BUYUK kaldirac. Ayni giris/stop/sure ile
    # yalnizca hedefi kaldirinca +48.5R -> +151.5R; sure 4->10 gun ile
    # +315R. V3 tam bu hucreyi canli olcer: STOP AYNEN KALIR (1.0x),
    # hedef YOK, sure ~10 islem gunu (70 saatlik bar).
    "V3_ORTA": {"mode": "wide", "stop_mult": 1.0, "max_bars": 70},
}


@dataclass
class LabResult:
    status: str                 # PENDING/FILLED/CLOSED
    outcome: str | None = None  # WIN/LOSS/EXPIRED/NOT_FILLED/AMBIGUOUS
    fill_price: float | None = None
    exit_price: float | None = None
    r_gross: float | None = None
    r_net: float | None = None
    closed_ts: int | None = None
    legs: list | None = None


def _leg_cost_r(price: float, frac: float, shares: float, risk_ref: float) -> float:
    """Tek bacagin maliyeti R cinsinden (sabit ucret + kayma)."""
    notional = price * shares * frac
    return (FEE_PER_TRADE + notional * SLIP_PCT) / risk_ref


def replay(sig: dict, candles: list[dict], variant: str,
           fill_window: int) -> LabResult:
    """Saf yeniden oynatim. sig: signals tablosu satiri; candles:
    entry_candle_ts SONRASI 1h mumlar (ts artan)."""
    cfg = VARIANTS[variant]
    is_long = sig["direction"] == "LONG"
    entry_min, entry_max = sig["entry_min"], sig["entry_max"]
    ref = entry_max if is_long else entry_min          # kotu uc
    risk0 = (ref - sig["stop_loss"]) if is_long else (sig["stop_loss"] - ref)
    if risk0 <= 0:
        return LabResult("CLOSED", "AMBIGUOUS", r_gross=0.0, r_net=0.0)
    if cfg["mode"] == "wide":
        stop = ref - cfg["stop_mult"] * risk0 if is_long \
            else ref + cfg["stop_mult"] * risk0
        tp1 = tp2 = None
        max_bars = cfg["max_bars"]
    else:
        stop, tp1, tp2 = sig["stop_loss"], sig["tp1"], sig["tp2"]
        max_bars = cfg["rest_max_bars"]

    fill = None
    fill_i = None
    legs: list[dict] = []
    remaining = 1.0
    r_acc = 0.0

    for i, c in enumerate(candles):
        just_filled = False
        if fill is None:
            touched = (c["low"] <= entry_min) if is_long else (c["high"] >= entry_max)
            if touched:
                fill = entry_max if is_long else entry_min
                if is_long and c["open"] < entry_min:
                    fill = c["open"]
                elif not is_long and c["open"] > entry_max:
                    fill = c["open"]
                fill_i = i
                # v4.22: dolum barinda cikis kontrolu atlanmaz (canli
                # tracker ile BIREBIR; test_v0_mirrors_live guvencesi).
                just_filled = True
            elif i + 1 >= fill_window:
                return LabResult("CLOSED", "NOT_FILLED", r_gross=0.0, r_net=0.0)
            else:
                continue

        risk = (fill - stop) if is_long else (stop - fill)
        if cfg["mode"] == "wide":
            # canli risk tabani (sinyalin kendi stop'u) ile R tutarliligi:
            # varyantin stop'u genis ama R payda olarak CANLI riski
            # kullanir - boylece V0/V1/V2 ayni olcekte kiyaslanir.
            risk = (fill - sig["stop_loss"]) if is_long \
                else (sig["stop_loss"] - fill)
        if risk <= 0:
            return LabResult("CLOSED", "AMBIGUOUS", fill_price=fill,
                             r_gross=0.0, r_net=0.0)
        shares = REF_RISK / risk

        hit_stop = (c["low"] <= stop) if is_long else (c["high"] >= stop)
        tp_now = tp1 if (tp1 is not None and remaining == 1.0) else tp2
        hit_tp = (tp_now is not None and
                  ((c["high"] >= tp_now) if is_long else (c["low"] <= tp_now)))
        # v4.22 GAP SIRASI (canli tracker ile birebir): acilis stop/hedef
        # OTESINDEYSE sira bilinir -> AMBIGUOUS degil, acilistan cikis.
        gap_stop = (not just_filled
                    and ((c["open"] < stop) if is_long else (c["open"] > stop)))
        gap_tp = (not just_filled and tp_now is not None
                  and ((c["open"] > tp_now) if is_long else (c["open"] < tp_now)))
        if just_filled:
            # dolum barinda: gap dallari kapali (acilis dolumdan onceydi);
            # stop+TP -> AMBIGUOUS, yalniz stop -> zarar, yalniz TP ->
            # iyimser WIN yazilmaz, pozisyon acik kalir (tracker ile ayni).
            if hit_stop and hit_tp:
                return LabResult("CLOSED", "AMBIGUOUS", fill_price=fill,
                                 r_gross=round(r_acc, 3),
                                 r_net=round(r_acc, 3),
                                 closed_ts=c["ts"], legs=legs)
            if hit_stop:
                pnl = ((stop - fill) if is_long else (fill - stop)) / risk
                r_acc += pnl * remaining
                legs.append({"px": stop, "frac": remaining, "why": "STOP",
                             "ts": c["ts"]})
                return _finish(sig, fill, stop, r_acc, legs, shares, c["ts"],
                               "LOSS" if r_acc < 0 else "WIN")
            hit_tp = False        # dolum barindaki TP'ye itibar edilmez
        if (not just_filled) and hit_stop and hit_tp \
                and not gap_stop and not gap_tp:
            # v4.22: kismi bacak GERCEKLESMISSE (V1'de TP1 alinmis) maliyetli
            # muhasebe _finish ile yapilir; sonuc yine AMBIGUOUS etiketlidir
            # ama gerceklesen bacagin R'i ve maliyetleri artik kaybolmaz.
            if legs:
                return _finish(sig, fill, fill, r_acc, legs, shares, c["ts"],
                               "AMBIGUOUS")
            return LabResult("CLOSED", "AMBIGUOUS", fill_price=fill,
                             r_gross=round(r_acc, 3), r_net=round(r_acc, 3),
                             closed_ts=c["ts"], legs=legs)
        if gap_stop or (hit_stop and not gap_tp):
            px = stop
            if is_long and c["open"] < stop:
                px = c["open"]
            elif not is_long and c["open"] > stop:
                px = c["open"]
            pnl = ((px - fill) if is_long else (fill - px)) / risk
            r_acc += pnl * remaining
            legs.append({"px": px, "frac": remaining, "why": "STOP", "ts": c["ts"]})
            return _finish(sig, fill, px, r_acc, legs, shares, c["ts"],
                           "LOSS" if r_acc < 0 else "WIN")
        if hit_tp:
            px = tp_now
            if is_long and c["open"] > tp_now:
                px = c["open"]
            elif not is_long and c["open"] < tp_now:
                px = c["open"]
            pnl = ((px - fill) if is_long else (fill - px)) / risk
            frac = cfg.get("tp1_frac", 1.0) if remaining == 1.0 else remaining
            r_acc += pnl * frac
            legs.append({"px": px, "frac": frac, "why": "TP", "ts": c["ts"]})
            remaining = round(remaining - frac, 6)
            if remaining <= 0 or tp2 is None:
                return _finish(sig, fill, px, r_acc, legs, shares, c["ts"], "WIN")
            continue
        bars_held = i - fill_i
        if bars_held >= max_bars:
            px = c["close"]
            pnl = ((px - fill) if is_long else (fill - px)) / risk
            r_acc += pnl * remaining
            legs.append({"px": px, "frac": remaining, "why": "TIME", "ts": c["ts"]})
            return _finish(sig, fill, px, r_acc, legs, shares, c["ts"], "EXPIRED")
    if fill is None:
        return LabResult("PENDING")
    return LabResult("FILLED", fill_price=fill, legs=legs,
                     r_gross=round(r_acc, 3))


def _finish(sig, fill, last_px, r_acc, legs, shares, ts, outcome) -> LabResult:
    cost = _leg_cost_r(fill, 1.0, shares, REF_RISK)          # giris bacagi
    for L in legs:
        cost += _leg_cost_r(L["px"], L["frac"], shares, REF_RISK)
    return LabResult("CLOSED", outcome, fill_price=fill, exit_price=last_px,
                     r_gross=round(r_acc, 3), r_net=round(r_acc - cost, 3),
                     closed_ts=ts, legs=legs)


class ExitLab:
    """EOD'de kosar: lab kapsamindaki sinyalleri varyantlarla oynatir."""

    def __init__(self, db, md, tracker, mtf: str = "1h",
                 fill_window: int = 12,
                 default_start: str = "2026-08-03T00:00:00Z") -> None:
        self._db = db
        self._md = md
        self._tracker = tracker
        self._mtf = mtf
        self._fill_window = fill_window
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS exit_lab("
            "signal_id INTEGER, variant TEXT, status TEXT, outcome TEXT,"
            "fill_price REAL, exit_price REAL, r_gross REAL, r_net REAL,"
            "closed_ts INTEGER, legs_json TEXT, updated REAL,"
            "PRIMARY KEY(signal_id, variant))")
        # v4.1.6: BASLANGIC SABIT OLMALI. Eskiden "ilk kurulumda bugun"
        # yaziliyordu; gist geri yuklemesi meta satirini silince tarih
        # ILERI kayiyor ve onceki gunlerin sinyalleri laboratuvar
        # kapsamindan DUSUYORDU (4 Agu'da 3 Agu kohortu kayboldu).
        # Artik varsayilan kodun icinde sabit; meta yalnizca override.
        row = self._db.query_one(
            "SELECT value FROM meta WHERE key='exit_lab_start'")
        self.lab_start = (row["value"] if row else default_start)
        self._db.execute(
            "INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)",
            ("exit_lab_start", self.lab_start))

    def _lab_signals(self) -> list[dict]:
        return self._db.query(
            "SELECT * FROM signals WHERE blocked=0 AND created_utc>=? "
            "ORDER BY id", (self.lab_start,))

    def run(self, today=None) -> dict:
        sigs = self._lab_signals()
        # bitmemis varyanti olan semboller icin mum arsivini tazele
        # (sembol izleme listesinden dusmus olabilir -> arsiv durur)
        pending_syms = sorted({
            s["symbol"] for s in sigs
            if any(self._state(s["id"], v) not in ("CLOSED",)
                   for v in VARIANTS)})
        if pending_syms:
            try:
                fresh = self._md.get_hourly_bulk(pending_syms)
                for series in fresh.values():
                    self._tracker.record_candles(series)
            except Exception:
                log.exception(kv(event="exit_lab_fetch_failed"))
        done = 0
        for s in sigs:
            candles = self._db.query(
                "SELECT * FROM candles WHERE symbol=? AND interval=? AND ts>? "
                "ORDER BY ts ASC", (s["symbol"], self._mtf,
                                    s["entry_candle_ts"]))
            if not candles:
                continue
            for v in VARIANTS:
                if self._state(s["id"], v) == "CLOSED":
                    continue
                res = replay(s, candles, v, self._fill_window)
                self._upsert(s["id"], v, res)
                if res.status == "CLOSED":
                    done += 1
        log.info(kv(event="exit_lab_run", signals=len(sigs), closed_now=done))
        return {"signals": len(sigs), "closed_now": done}

    def _state(self, sid: int, variant: str) -> str | None:
        r = self._db.query_one(
            "SELECT status FROM exit_lab WHERE signal_id=? AND variant=?",
            (sid, variant))
        return r["status"] if r else None

    def _upsert(self, sid: int, variant: str, r: LabResult) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO exit_lab(signal_id,variant,status,outcome,"
            "fill_price,exit_price,r_gross,r_net,closed_ts,legs_json,updated) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (sid, variant, r.status, r.outcome, r.fill_price, r.exit_price,
             r.r_gross, r.r_net, r.closed_ts,
             json.dumps(r.legs) if r.legs else None, time.time()))

    def summary(self) -> dict:
        """Varyantlar + V0 (canli defter) AYNI sinyal kumesinde."""
        sigs = self._lab_signals()
        ids = [s["id"] for s in sigs]
        out = {"lab_start": self.lab_start, "signals": len(ids),
               "variants": {}}
        if not ids:
            out["variants"] = {k: {"n_decided": 0, "net_r": 0.0, "wins": 0,
                                   "open": 0}
                               for k in ("V0_CANLI", *VARIANTS)}
            return out
        # V0 = canli sonuclar (Net-R, tracker maliyet modeliyle)
        v0 = {"n_decided": 0, "net_r": 0.0, "wins": 0, "open": 0}
        for s in sigs:
            if s["status"] != "CLOSED":
                v0["open"] += 1
            elif s["outcome"] in ("WIN", "LOSS", "EXPIRED"):
                v0["n_decided"] += 1
                r = (s["r_multiple"] or 0.0) - (self._tracker.cost_r(s) or 0.0)
                v0["net_r"] += r
                v0["wins"] += 1 if r > 0 else 0
        v0["net_r"] = round(v0["net_r"], 2)
        out["variants"]["V0_CANLI"] = v0
        for v in VARIANTS:
            rows = self._db.query(
                "SELECT status, outcome, r_net FROM exit_lab WHERE variant=? "
                "AND signal_id IN (%s)" % ",".join("?" * len(ids)),
                (v, *ids))
            agg = {"n_decided": 0, "net_r": 0.0, "wins": 0, "open": 0}
            for r in rows:
                if r["status"] != "CLOSED":
                    agg["open"] += 1
                elif r["outcome"] in ("WIN", "LOSS", "EXPIRED"):
                    agg["n_decided"] += 1
                    agg["net_r"] += r["r_net"] or 0.0
                    agg["wins"] += 1 if (r["r_net"] or 0) > 0 else 0
            agg["net_r"] = round(agg["net_r"], 2)
            out["variants"][v] = agg
        return out
