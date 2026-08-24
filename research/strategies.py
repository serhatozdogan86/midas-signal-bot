"""
ALTI STRATEJI - hepsi buyuk kurumlarin veya perakende tarafin fiilen
kullandigi aileler, KANONIK parametrelerle (optimize edilmedi; optimize
etseydik "gecmise en iyi uydurulan"i olcmus olurduk).

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

6) VOLATILITE SIKISMASI KIRILIMI (Squeeze) - TradingView'in en begenilen
   mekanizmasi (LazyBear) + volatilite kumelenmesi literaturu; bybit
   arastirmasinin da 1. tercihi. BB(20,2) bantlari KC(20,1.5) icine
   girince "sikisik"; sikisma >=6 bar surup fiyat sikisma araliginin
   ustunde kapatinca LONG. Hipotez 9 olarak ON-KAYITLI (17 Agu).

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


# ---------------------------------------------------------------- 6
def squeeze_breakout(bars: pd.DataFrame, direction: str,
                     bb_n: int = 20, bb_k: float = 2.0,
                     kc_n: int = 20, kc_k: float = 1.5,
                     min_bars: int = 6) -> pd.Series:
    """VOLATILITE SIKISMASI KIRILIMI (hipotez 9, on-kayit 17 Agu).

    Tanim ON-KAYITTAN aynen alindi (research-log.md sat. 44), burada
    hicbir parametre "iyilestirilmedi" - optimize etseydik gecmise en
    iyi uydurulani olcmus olurduk (harness ilkesi 5):
      sikisma = BB(20,2) bantlari KC(20,1.5) ICINDE (LazyBear kanonigi;
      iki kanalin merkezi de SMA20, KC yarigenisligi 1.5 x SMA20(TR))
      tetik   = sikisma >= 6 bar surup fiyat sikisma araliginin USTUNDE
                kapatinca LONG (ayna: ALTINDA kapanis -> SHORT)

    Look-ahead YOK: i barinin sinyali yalnizca <= i verisini kullanir
    (sikisma dizisi i-1'de biter, aralik i-1'e kadarki high/low'dur);
    harness girisi zaten i+1 acilisindan yapar.

    Tekrar YOK: ayni sikismadan yalnizca ILK kirilim sinyal olur -
    aksi halde sikisma devam ederken her bar sinyal uretirdi (52H
    zirvesindeki 'fresh' korumasinin ayni gerekcesi).

    NOT (bilincli): on-kayitta "stop araligin alt ucu" yaziyor; O KURAL
    S6'nin strategy_lab uygulamasina aittir. Burada TUM stratejiler
    ORTAK cikis mekanigiyle kosar (harness tasarim ilkesi) - yoksa
    "giris mi cikis mi kazandirdi" ayrilamaz. Kiyas gecerse S6'nin
    kendi stop'u strategy_lab'de olculur.

    IKIZ FARKI (bybit S11, ikiz-depo-notu 24 Agu): bybit tetigi yalnizca
    sikisma COZULUNCE alir ve ayrica momentum teyidi arar. midas'in
    on-kaydinda ikisi de YOK - burada on-kayit metnine sadik kalindi;
    daha dar varyant sonuclara bakildiktan SONRA "kural esnetme" olurdu.
    Ikiz varyanti ayri bir hipotez olarak olculebilir.
    """
    if direction not in ("LONG", "SHORT"):
        return pd.Series(False, index=bars.index)
    c, h, low = bars["close"], bars["high"], bars["low"]
    # IKI KANALIN ORTASI DA SMA20 (LazyBear kanonigi; ikiz bybit S11 ile
    # ayni). Ilk yazimda KC merkezi EMA'ydi - o zaman "BB, KC icinde"
    # sinavi genislige DEGIL merkezlerin kaymasina da duyarli oluyordu,
    # yani sikismayi olcmek yerine sikisma+egilim karisimi olcuyordu.
    # Duzeltme SONUCA BAKILMADAN yapildi (24 Agu, ikiz karsilastirmasi).
    mid = c.rolling(bb_n).mean()
    sd = c.rolling(bb_n).std(ddof=0)
    bb_up, bb_dn = mid + bb_k * sd, mid - bb_k * sd
    rng = pd.concat([h - low, (h - c.shift()).abs(),
                     (low - c.shift()).abs()], axis=1).max(axis=1)
    atr_kc = rng.rolling(kc_n).mean()
    kc_up, kc_dn = mid + kc_k * atr_kc, mid - kc_k * atr_kc
    squeezed = ((bb_up < kc_up) & (bb_dn > kc_dn)).fillna(False).values

    hv, lv, cv = h.values, low.values, c.values
    out = np.zeros(len(bars), dtype=bool)
    run = 0                 # i-1'de biten kesintisiz sikisma uzunlugu
    hi = lo = None          # o sikismanin aralik ust/alt ucu
    fired = False           # bu sikismadan sinyal alindi mi
    for i in range(len(bars)):
        if run >= min_bars and not fired and np.isfinite(cv[i]):
            if direction == "LONG" and cv[i] > hi:
                out[i], fired = True, True
            elif direction == "SHORT" and cv[i] < lo:
                out[i], fired = True, True
        if squeezed[i]:
            run += 1
            hi = hv[i] if hi is None else max(hi, hv[i])
            lo = lv[i] if lo is None else min(lo, lv[i])
        else:
            # sikisma bitti: kirilimi bekleme penceresi de biter ancak
            # cikis barinin KENDISI tetik olabilir (yukarida bakildi).
            run, hi, lo, fired = 0, None, None, False
    return pd.Series(out, index=bars.index)


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
    "6_SQUEEZE_KIRILIM": squeeze_breakout,
    "0_BIZIM_VEKIL": bizim_vekil,
}
