"""
STRATEJI LABORATUVARI (v3.21) - KATMAN 2.

Cikis laboratuvari (exit_lab) ayni girise farkli CIKISLAR uyguluyordu.
Burada tersi: farkli GIRIS stratejileri, hepsine AYNI cikis mekanigi.
Boylece fark yalnizca "hangi hisseye, ne zaman girilir"den gelir.

ADAYLAR (research/ backtestinde olculen aileler, kanonik parametreler):
  S1_MOMENTUM  12-1 kesitsel momentum (Jegadeesh-Titman; AQR).
               Evrenin momentum ust %10'u, HAFTALIK yenileme.
               Backtest'te tek KARARLI pozitif giris (NW t=3.3).
  S2_DONCHIAN  20 gunluk zirve kirilimi (Turtle System 1; CTA'lar).
  S3_VOL_BREAK 20g zirve + hacim >= 2x ortalama (sinirda umutlu, t=1.98).
  S4_RSI2      200G MA ustunde + RSI(2)<10 (Connors; kisa vadeli donus).

ORTAK CIKIS (hepsinde ayni, canli V0 ile ayni ruh):
  giris  = sinyal gununun ERTESI acilisi (look-ahead yok)
  stop   = giris - 1.2 x ATR14      hedef = giris + 1.0 x ATR14
  sure   = 4 islem gunu (time-stop)
  gun ici sira KOTUMSER: ayni gun stop ve hedef -> STOP sayilir
  gap    = acilis stop otesindeyse cikis ACILISTAN
  maliyet= Midas modeli (2x1.50$ + 5bp, 10k referans) R'ye cevrilir

IKI GORUNUM (kullanici talebi):
  TAVANSIZ  tum evren taranir, her sinyal alinir -> stratejinin HAM edge'i
  TAVANLI   portfoy kurallarimiz uygulanir (gunde en fazla
            MAX_DAILY_SIGNALS, ayni anda en fazla MAX_OPEN_SIGNALS)
            -> gercekte uygulanabilir hali. Secim sirasi deterministik:
            gunun sinyalleri SEMBOL ALFABETIK siralanir (skor uydurmuyoruz).

DURUSTLUK NOTU: tarihsel pencere BACKTEST'tir, canli kanit degildir.
Kohort penceresi (lab_start sonrasi) ayri raporlanir; karar YALNIZ
kohort penceresine bakilarak verilir.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.logging_setup import kv

log = logging.getLogger("strategy_lab")

FEE_USD = 1.50 * 2
REF_NOTIONAL = 10_000.0
SLIP_PCT = 0.0005
COST_PCT = FEE_USD / REF_NOTIONAL + SLIP_PCT      # %0.08 gidis-donus

ATR_N = 14
STOP_MULT = 1.2
TP_MULT = 1.0
MAX_HOLD = 4

STRATEGIES = ("S1_MOMENTUM", "S2_DONCHIAN", "S3_VOL_BREAK", "S4_RSI2",
              "S5_MOM_WIDE")

# Yurutme profilleri: S1-S4 canli cikisla (V0 esdegeri) kosar ki fark
# YALNIZ girisden gelsin. S5 ayni S1 girisidir ama V2 (genis stop,
# hedefsiz, uzun tutma) cikisiyla - "en iyi giris + en iyi cikis"
# birlesimi kombinasyon olarak olculur.
EXEC = {
    "V0": {"stop_mult": 1.2, "tp_mult": 1.0, "max_hold": 4},
    "V2": {"stop_mult": 2.0, "tp_mult": None, "max_hold": 20},
}
EXEC_OF = {"S1_MOMENTUM": "V0", "S2_DONCHIAN": "V0", "S3_VOL_BREAK": "V0",
           "S4_RSI2": "V0", "S5_MOM_WIDE": "V2"}
LABELS = {
    "S1_MOMENTUM": "S1 · kesitsel momentum",
    "S2_DONCHIAN": "S2 · Donchian kırılımı",
    "S3_VOL_BREAK": "S3 · hacimli kırılım",
    "S4_RSI2": "S4 · RSI(2) dönüş",
    "S5_MOM_WIDE": "S5 · momentum + geniş çıkış",
}


# --------------------------------------------------------- gostergeler
def atr(bars: list[dict], n: int = ATR_N) -> list[float | None]:
    out: list[float | None] = [None] * len(bars)
    trs: list[float] = []
    for i, b in enumerate(bars):
        if i == 0:
            trs.append(b["high"] - b["low"])
        else:
            pc = bars[i - 1]["close"]
            trs.append(max(b["high"] - b["low"], abs(b["high"] - pc),
                           abs(b["low"] - pc)))
        if i >= n - 1:
            out[i] = sum(trs[i - n + 1:i + 1]) / n
    return out


def sma(vals: list[float], n: int, i: int) -> float | None:
    if i + 1 < n:
        return None
    return sum(vals[i - n + 1:i + 1]) / n


def rsi_wilder(closes: list[float], n: int) -> list[float | None]:
    out: list[float | None] = [None] * len(closes)
    if len(closes) < n + 1:
        return out
    up = dn = 0.0
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        g, ls = max(d, 0.0), max(-d, 0.0)
        if i <= n:
            up += g / n
            dn += ls / n
            if i == n:
                out[i] = 100.0 if dn == 0 else 100 - 100 / (1 + up / dn)
            continue
        up = (up * (n - 1) + g) / n
        dn = (dn * (n - 1) + ls) / n
        out[i] = 100.0 if dn == 0 else 100 - 100 / (1 + up / dn)
    return out


# ----------------------------------------------------- sinyal ureticiler
def signals_donchian(bars: list[dict], n: int = 20) -> list[bool]:
    out = [False] * len(bars)
    for i in range(n, len(bars)):
        hi = max(b["high"] for b in bars[i - n:i])
        out[i] = bars[i]["close"] > hi
    return out


def signals_vol_break(bars: list[dict], n: int = 20,
                      vol_mult: float = 2.0) -> list[bool]:
    out = [False] * len(bars)
    for i in range(n, len(bars)):
        hi = max(b["high"] for b in bars[i - n:i])
        vavg = sum(b["volume"] for b in bars[i - n:i]) / n
        out[i] = (bars[i]["close"] > hi and vavg > 0
                  and bars[i]["volume"] >= vol_mult * vavg)
    return out


def signals_rsi2(bars: list[dict]) -> list[bool]:
    closes = [b["close"] for b in bars]
    r = rsi_wilder(closes, 2)
    out = [False] * len(bars)
    for i in range(len(bars)):
        ma200 = sma(closes, 200, i)
        if ma200 is None or r[i] is None:
            continue
        out[i] = closes[i] > ma200 and r[i] < 10
    return out


def momentum_12_1(bars: list[dict], i: int) -> float | None:
    """Son 12 ayin getirisi, SON AY HARIC (21/252 islem gunu)."""
    if i < 252:
        return None
    old, recent = bars[i - 252]["close"], bars[i - 21]["close"]
    if old <= 0:
        return None
    return recent / old - 1


def _breakout_scores(bars: list[dict], a14: list[float | None],
                     n: int = 20) -> list[float]:
    """Kirilim gucu: (kapanis - onceki n gun zirvesi) / ATR."""
    out = [0.0] * len(bars)
    for i in range(n, len(bars)):
        hi = max(b["high"] for b in bars[i - n:i])
        if a14[i]:
            out[i] = (bars[i]["close"] - hi) / a14[i]
    return out


def _volume_scores(bars: list[dict], n: int = 20) -> list[float]:
    out = [0.0] * len(bars)
    for i in range(n, len(bars)):
        v = sum(b["volume"] for b in bars[i - n:i]) / n
        if v > 0:
            out[i] = bars[i]["volume"] / v
    return out


# ------------------------------------------------------------ yurutme
@dataclass(slots=True)
class Trade:
    strategy: str
    symbol: str
    signal_date: str
    entry_date: str
    entry: float
    stop: float
    tp: float
    exit_price: float | None = None
    exit_date: str | None = None
    r_net: float | None = None
    outcome: str | None = None
    score: float = 0.0        # tavan secimi icin kalite olcusu (buyuk = iyi)


def simulate_symbol(symbol: str, bars: list[dict], sig: list[bool],
                    strategy: str,
                    scores: list[float] | None = None,
                    stop_mult: float = STOP_MULT,
                    tp_mult: float | None = TP_MULT,
                    max_hold: int = MAX_HOLD) -> list[Trade]:
    """Sinyal gunu t -> giris t+1 acilisi. Saf fonksiyon."""
    a = atr(bars)
    out: list[Trade] = []
    n = len(bars)
    for i in range(n - 1):
        if not sig[i] or a[i] is None or a[i] <= 0:
            continue
        entry = bars[i + 1]["open"]
        if not entry or entry <= 0:
            continue
        risk = stop_mult * a[i]
        stop = entry - risk
        tp = (entry + tp_mult * a[i]) if tp_mult is not None else None
        px = None
        why = None
        j_end = min(i + 1 + max_hold, n)
        for j in range(i + 1, j_end):
            b = bars[j]
            if b["open"] <= stop:                 # gap ile stop otesi
                px, why = b["open"], "GAP_STOP"
            elif b["low"] <= stop:                # kotumser: stop once
                px, why = stop, "STOP"
            elif tp is not None and b["high"] >= tp:
                px, why = tp, "TP"
            if px is not None:
                exit_date = b["date"]
                break
        if px is None:
            b = bars[j_end - 1]
            px, why, exit_date = b["close"], "TIME", b["date"]
        r_gross = (px - entry) / risk
        cost_r = (COST_PCT * entry) / risk
        out.append(Trade(strategy=strategy, symbol=symbol,
                         signal_date=bars[i]["date"],
                         entry_date=bars[i + 1]["date"], entry=entry,
                         stop=stop, tp=(tp if tp is not None else 0.0), exit_price=px,
                         exit_date=exit_date,
                         r_net=round(r_gross - cost_r, 4),
                         score=(scores[i] if scores else 0.0),
                         outcome=("WIN" if r_gross > 0 else
                                  "LOSS" if why in ("STOP", "GAP_STOP")
                                  else "EXPIRED")))
    return out


def apply_caps(trades: list[Trade], max_daily: int, max_open: int,
               ranked: bool = True) -> list[Trade]:
    """Portfoy tavanlari: gunluk yeni sinyal + es zamanli acik siniri.

    v3.22: SECIM SIRASI ONEMLI. Once alfabetikti; S4 vakasi gosterdi ki
    tavansiz +79R olan strateji, tavan RASTGELE secerse -148R'ye
    dusuyor. Artik varsayilan KALITEYE GORE (score buyukten kucuge);
    ranked=False alfabetik (rastgele vekili) - ikisi kiyaslanabilsin
    diye ikisi de olculur.
    """
    taken: list[Trade] = []
    open_until: list[str] = []          # acik islemlerin cikis tarihleri
    by_day: dict[str, list[Trade]] = {}
    for t in trades:
        by_day.setdefault(t.entry_date, []).append(t)
    for day in sorted(by_day):
        open_until = [d for d in open_until if d >= day]
        slots = max_open - len(open_until)
        if slots <= 0:
            continue
        order = (sorted(by_day[day], key=lambda x: (-x.score, x.symbol))
                 if ranked else sorted(by_day[day], key=lambda x: x.symbol))
        for t in order[:min(max_daily, slots)]:
            taken.append(t)
            open_until.append(t.exit_date or day)
    return taken


def summarize(trades: list[Trade], since: str | None = None) -> dict:
    sel = [t for t in trades if since is None or t.signal_date >= since]
    if not sel:
        return {"n": 0, "net_r": 0.0, "win_rate": None, "expectancy": None,
                "max_dd_r": 0.0}
    rs = [t.r_net or 0.0 for t in sorted(sel, key=lambda x: x.exit_date or "")]
    eq, peak, dd = 0.0, 0.0, 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    wins = sum(1 for r in rs if r > 0)
    return {"n": len(rs), "net_r": round(sum(rs), 2),
            "win_rate": round(wins / len(rs), 3),
            "expectancy": round(sum(rs) / len(rs), 3),
            "max_dd_r": round(dd, 2)}


@dataclass
class StrategyLab:
    """EOD'de tum evreni tarar; tavansiz ve tavanli sonuclari uretir."""

    settings: object
    lab_start: str = "2026-08-04"
    last: dict = field(default_factory=dict)

    def run(self, daily: dict) -> dict:
        """daily: {symbol: KlineSeries}. Saf hesap + ozet; I/O yok.

        BELLEK NOTU (v4.4): eskiden tum evrenin mumlari AYNI ANDA
        sozluk-listesi olarak tutuluyordu; olcum 300 sembol icin ~207 MB
        zirve gosterdi ve Render'in 512 MB'lik sinirinda servis
        OOM ile yeniden basliyordu. Artik iki gecis yapilir ve her
        gecis sembol basina gecici mum listesi uretip HEMEN birakir;
        bellekte kalan tek buyuk yapi momentum tablosudur.
        """
        universe = sorted(daily)

        def bars_of(sym):
            cs = daily[sym].candles
            if len(cs) < 60:
                return None
            cs = cs[-420:]          # momentum 252 + tampon; fazlasi gereksiz
            return [{"date": _iso(c.ts), "open": c.open, "high": c.high,
                     "low": c.low, "close": c.close, "volume": c.volume}
                    for c in cs]

        # --- GECIS 1: yalniz kesitsel momentum tablosu ---
        mom: dict[str, dict[str, float]] = {}
        n_ok = 0
        for sym in universe:
            bars = bars_of(sym)
            if bars is None:
                continue
            n_ok += 1
            for i in range(len(bars)):
                m = momentum_12_1(bars, i)
                if m is not None:
                    mom.setdefault(bars[i]["date"], {})[sym] = m
            del bars                     # hemen birak

        top_decile: dict[str, set[str]] = {}
        for day, vals in mom.items():
            if len(vals) < 30:
                continue
            k = max(1, int(len(vals) * 0.1))
            top_decile[day] = {s for s, _ in sorted(
                vals.items(), key=lambda kv: kv[1], reverse=True)[:k]}
        mom.clear()                      # tablo artik gereksiz

        # --- GECIS 2: sinyaller + yurutme (sembol basina gecici) ---
        all_trades: dict[str, list[Trade]] = {k: [] for k in STRATEGIES}
        for sym in universe:
            bars = bars_of(sym)
            if bars is None:
                continue
            gens = {
                "S1_MOMENTUM": [
                    (b["date"] in top_decile and sym in top_decile[b["date"]]
                     and _is_monday(b["date"])) for b in bars],
                "S2_DONCHIAN": signals_donchian(bars),
                "S3_VOL_BREAK": signals_vol_break(bars),
                "S4_RSI2": signals_rsi2(bars),
            }
            gens["S5_MOM_WIDE"] = gens["S1_MOMENTUM"]      # AYNI giris
            closes = [b["close"] for b in bars]
            r2 = rsi_wilder(closes, 2)
            a14 = atr(bars)
            scores = {
                "S1_MOMENTUM": [(momentum_12_1(bars, i) or 0.0)
                                for i in range(len(bars))],
                "S2_DONCHIAN": _breakout_scores(bars, a14),
                "S3_VOL_BREAK": _volume_scores(bars),
                "S4_RSI2": [(100.0 - (r2[i] if r2[i] is not None else 100.0))
                            for i in range(len(bars))],
            }
            scores["S5_MOM_WIDE"] = scores["S1_MOMENTUM"]
            for name, sig in gens.items():
                cfg = EXEC[EXEC_OF[name]]
                all_trades[name].extend(
                    simulate_symbol(sym, bars, sig, name, scores[name],
                                    stop_mult=cfg["stop_mult"],
                                    tp_mult=cfg["tp_mult"],
                                    max_hold=cfg["max_hold"]))
            del bars, gens, scores, closes, r2, a14

        md = getattr(self.settings, "MAX_DAILY_SIGNALS", 6)
        mo = getattr(self.settings, "MAX_OPEN_SIGNALS", 10)
        out = {"lab_start": self.lab_start, "universe": n_ok,
               "strategies": {}}
        for name in STRATEGIES:
            tr = all_trades[name]
            capped = apply_caps(tr, md, mo, ranked=True)
            capped_rnd = apply_caps(tr, md, mo, ranked=False)
            out["strategies"][name] = {
                "label": LABELS[name],
                "exit": EXEC_OF[name],
                "kohort": {"tavansiz": summarize(tr, self.lab_start),
                           "tavanli": summarize(capped, self.lab_start)},
                "tarihsel": {"tavansiz": summarize(tr),
                             "tavanli": summarize(capped),
                             "tavanli_rastgele": summarize(capped_rnd)},
            }
            all_trades[name] = []        # ozet alindi, ham islemleri birak
        self.last = out
        log.info(kv(event="strategy_lab_run", universe=n_ok,
                    **{k: out["strategies"][k]["tarihsel"]["tavansiz"]["n"]
                       for k in STRATEGIES}))
        return out


def _iso(ts_ms: int) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%d")


def _is_monday(date_str: str) -> bool:
    from datetime import date
    y, m, d = (int(x) for x in date_str.split("-"))
    return date(y, m, d).weekday() == 0
