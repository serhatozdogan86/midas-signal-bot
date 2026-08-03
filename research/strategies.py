"""
BES STRATEJI - hepsi buyuk kurumlarin fiilen kullandigi aileler,
KANONIK parametrelerle (optimize edilmedi; optimize etseydik "gecmise
en iyi uydurulan"i olcmus olurduk).

1) DONCHIAN / TURTLE KIRILIMI  - trend takibi (CTA'lar: Winton, Man AHL,
   Chesapeake). Kural: 20 gunluk en yuksegin uzerinde kapanis -> LONG;
   20 gunluk en dusugun altinda -> SHORT. (Turtle System 1)

2) KESITSEL MOMENTUM 12-1      - Jegadeesh-Titman; AQR/Dimensional'in
   momentum fonlarinin omurgasi. Son 12 ayin getirisi (son ay HARIC)
   evrenin ust %10'undaysa -> LONG, alt %10 -> SHORT. Haftalik yenileme.

3) KISA VADELI ORTALAMAYA DONUS (RSI-2) - Connors; prop firmalarinin ve
   piyasa yapicilarinin klasigi. 200G MA ustunde + RSI(2) < 10 -> LONG
   (ayna: 200G altinda + RSI(2) > 90 -> SHORT).

4) PIYASA-NOTR REZIDUEL (stat-arb) - Morgan Stanley'in orijinal
   istatistiksel arbitraji; bugun Two Sigma/DE Shaw ailesinin temeli.
   60 gunluk beta ile SPY'a gore artik getiri; 10 gunluk artigin
   z-skoru < -2 -> LONG (asiri satilmis), > +2 -> SHORT.

5) 52-HAFTA ZIRVESI YAKINLIGI  - George & Hwang (2004); momentum
   fonlarinin "yeni zirve" filtresi. Fiyat 52 haftanin zirvesinin
   %2 yakininda + hacim teyidi -> LONG.

KIYAS TABANI:
- BIZIM_VEKIL: mevcut motorumuzun gunluk vekili (fiyat>50MA>200MA +
  20EMA'ya geri cekilme + RSI(3) asiriligi). BIREBIR DEGIL: canli
  motor 1h setup ve hacim teyidi kullaniyor; bu yalnizca gunluk
  yaklasik karsilik.
- SPY_ALKOY: al-tut (islem bazli degil, referans egri).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def rsi(close: pd.Series, n: int) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


# ---------------------------------------------------------------- 1
def donchian(bars: pd.DataFrame, direction: str, n: int = 20) -> pd.Series:
    hi = bars["high"].rolling(n).max().shift(1)
    lo = bars["low"].rolling(n).min().shift(1)
    if direction == "LONG":
        return bars["close"] > hi
    return bars["close"] < lo


# ---------------------------------------------------------------- 2
def xsec_momentum(bars: pd.DataFrame, direction: str,
                  rank_pct: pd.Series | None = None,
                  weekday: int = 0) -> pd.Series:
    """rank_pct: o gun evren icindeki 12-1 momentum yuzdelik dilimi
    (disaridan verilir; kesitsel oldugu icin tek sembolden hesaplanamaz).
    Haftalik yenileme: yalnizca pazartesileri sinyal."""
    if rank_pct is None:
        return pd.Series(False, index=bars.index)
    is_day = bars.index.dayofweek == weekday
    if direction == "LONG":
        return pd.Series((rank_pct >= 0.9).values & is_day, index=bars.index)
    return pd.Series((rank_pct <= 0.1).values & is_day, index=bars.index)


# ---------------------------------------------------------------- 3
def rsi2_reversion(bars: pd.DataFrame, direction: str) -> pd.Series:
    ma200 = bars["close"].rolling(200).mean()
    r = rsi(bars["close"], 2)
    if direction == "LONG":
        return (bars["close"] > ma200) & (r < 10)
    return (bars["close"] < ma200) & (r > 90)


# ---------------------------------------------------------------- 4
def residual_zscore(bars: pd.DataFrame, direction: str,
                    bench: pd.Series | None = None) -> pd.Series:
    if bench is None:
        return pd.Series(False, index=bars.index)
    r = bars["close"].pct_change()
    b = bench.reindex(bars.index).pct_change()
    cov = r.rolling(60).cov(b)
    var = b.rolling(60).var()
    beta = (cov / var).clip(-3, 3)
    resid = r - beta * b
    cum = resid.rolling(10).sum()
    z = (cum - cum.rolling(60).mean()) / cum.rolling(60).std()
    if direction == "LONG":
        return z < -2
    return z > 2


# ---------------------------------------------------------------- 5
def near_52w_high(bars: pd.DataFrame, direction: str) -> pd.Series:
    if direction != "LONG":                      # ayna tarafi anlamsiz
        return pd.Series(False, index=bars.index)
    hi52 = bars["high"].rolling(252).max()
    vol_ok = bars["volume"] > bars["volume"].rolling(20).mean()
    near = bars["close"] >= hi52 * 0.98
    fresh = near & ~near.shift(1).fillna(False)   # yalnizca ILK gun (spam yok)
    return fresh & vol_ok


# ------------------------------------------------------ kiyas tabani
def bizim_vekil(bars: pd.DataFrame, direction: str) -> pd.Series:
    """Mevcut motorun gunluk vekili (birebir degil - canlida 1h setup var)."""
    c = bars["close"]
    ma50, ma200 = c.rolling(50).mean(), c.rolling(200).mean()
    ema20 = c.ewm(span=20, adjust=False).mean()
    r3 = rsi(c, 3)
    if direction == "LONG":
        trend = (c > ma50) & (ma50 > ma200)
        pull = (bars["low"] <= ema20 * 1.01) & (r3 < 15)
        return trend & pull
    trend = (c < ma50) & (ma50 < ma200)
    pull = (bars["high"] >= ema20 * 0.99) & (r3 > 85)
    return trend & pull


REGISTRY = {
    "1_DONCHIAN_KIRILIM": donchian,
    "2_KESITSEL_MOMENTUM": xsec_momentum,
    "3_RSI2_DONUS": rsi2_reversion,
    "4_REZIDUEL_STATARB": residual_zscore,
    "5_52H_ZIRVE": near_52w_high,
    "0_BIZIM_VEKIL": bizim_vekil,
}
