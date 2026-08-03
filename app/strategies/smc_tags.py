"""
Smart Money Concepts (SMC) ETIKETLERI - v3.15

Bu modul KARARA KARISMAZ. Hicbir sinyali engellemez, hicbir esigi
degistirmez, signal_engine bu modulu IMPORT ETMEZ (test ile guvence
altinda). Tek isi: sinyal dogarken piyasa yapisinin SMC diliyle nasil
gorundugunu kaydetmek, boylece kohort dolunca "onunde likidite avi olan
sinyaller daha mi iyiydi?" sorusunu KENDI DEFTERIMIZDEN cevaplayabilelim.

Neden etiket, neden simdi degil karar: SMC kavramlarinin cogu oznel
tanimlidir; bizim disiplinimiz yanlislanabilirlik uzerine kurulu. Bu
yuzden yalnizca KESIN KODLANABILIR uc kavram alindi:

1) FVG (fair value gap / dengesizlik): uc mumluk boslugun ORTA mumun
   iki yanindaki mumlarla ortusmemesi.
   Bogа FVG: low[i] > high[i-2]   |   Ayi FVG: high[i] < low[i-2]

2) LIKIDITE AVI (liquidity sweep / stop avi): girisden once onceki bir
   swing dip/tepesinin DELINIP geri kazanilmasi. SMC'ye gore bu, zayif
   ellerin stoplarinin toplanmasidir ve hareketin devami beklenir.
   LONG icin: onceki swing dip delindi (low < pivot) ve `recover_bars`
   icinde kapanis o pivotun USTUNE dondu.

3) PRIM/ISKONTO KONUMU (premium/discount): girisin son `range_bars`
   araliginin neresinde oldugu (0 = dibin dibi, 1 = tepenin tepesi).
   SMC LONG icin iskontoyu (<0.5) tercih eder.

Not: order block, inducement, breaker gibi kavramlar BILINCLI olarak
disarida birakildi - tanimlari yoruma acik oldugu icin olcum degeri
tasimazlar.
"""
from __future__ import annotations


def _pivot_lows(lows: list[float], k: int) -> list[int]:
    """i, her iki yanindaki k barin hepsinden dusukse pivot dip."""
    out = []
    for i in range(k, len(lows) - k):
        seg = lows[i - k:i + k + 1]
        if lows[i] == min(seg) and seg.count(lows[i]) == 1:
            out.append(i)
    return out


def _pivot_highs(highs: list[float], k: int) -> list[int]:
    out = []
    for i in range(k, len(highs) - k):
        seg = highs[i - k:i + k + 1]
        if highs[i] == max(seg) and seg.count(highs[i]) == 1:
            out.append(i)
    return out


def find_fvg(highs: list[float], lows: list[float], direction: str,
             lookback: int = 12) -> dict | None:
    """Son `lookback` bar icindeki EN YENI yon-uyumlu FVG."""
    n = len(highs)
    if n < 3:
        return None
    start = max(2, n - lookback)
    for i in range(n - 1, start - 1, -1):
        if direction == "LONG" and lows[i] > highs[i - 2]:
            return {"bars_ago": n - 1 - i, "low": highs[i - 2], "high": lows[i],
                    "size": round(lows[i] - highs[i - 2], 4)}
        if direction == "SHORT" and highs[i] < lows[i - 2]:
            return {"bars_ago": n - 1 - i, "low": highs[i], "high": lows[i - 2],
                    "size": round(lows[i - 2] - highs[i], 4)}
    return None


def find_liquidity_sweep(highs: list[float], lows: list[float],
                         closes: list[float], direction: str,
                         pivot_k: int = 3, lookback: int = 20,
                         recover_bars: int = 3) -> dict | None:
    """Onceki swing seviyesinin delinip geri kazanilmasi."""
    n = len(closes)
    if n < pivot_k * 2 + 3:
        return None
    if direction == "LONG":
        pivots = _pivot_lows(lows, pivot_k)
        for p in reversed(pivots):
            level = lows[p]
            for i in range(p + pivot_k + 1, n):
                if n - 1 - i > lookback:
                    continue
                if lows[i] < level:                      # delindi
                    end = min(n, i + recover_bars + 1)
                    for j in range(i, end):
                        if closes[j] > level:            # geri kazanildi
                            return {"level": round(level, 4),
                                    "bars_ago": n - 1 - j,
                                    "depth": round(level - min(lows[i:end]), 4)}
                    break
    else:
        pivots = _pivot_highs(highs, pivot_k)
        for p in reversed(pivots):
            level = highs[p]
            for i in range(p + pivot_k + 1, n):
                if n - 1 - i > lookback:
                    continue
                if highs[i] > level:
                    end = min(n, i + recover_bars + 1)
                    for j in range(i, end):
                        if closes[j] < level:
                            return {"level": round(level, 4),
                                    "bars_ago": n - 1 - j,
                                    "depth": round(max(highs[i:end]) - level, 4)}
                    break
    return None


def range_position(highs: list[float], lows: list[float], price: float,
                   range_bars: int = 40) -> float | None:
    """0 = aralik dibi (iskonto), 1 = aralik tepesi (prim)."""
    if not highs or not lows or price is None:
        return None
    hi = max(highs[-range_bars:])
    lo = min(lows[-range_bars:])
    if hi <= lo:
        return None
    return round((price - lo) / (hi - lo), 3)


def tag_candles(candles, direction: str, entry: float | None = None) -> dict:
    """KlineSeries.candles (veya .high/.low/.close tasiyan herhangi bir
    nesne listesi) icin SMC etiketleri. Saf fonksiyon, I/O yok."""
    try:
        highs = [float(c.high) for c in candles]
        lows = [float(c.low) for c in candles]
        closes = [float(c.close) for c in candles]
    except Exception:
        return {}
    if len(closes) < 6:
        return {}
    ref = entry if entry is not None else closes[-1]
    fvg = find_fvg(highs, lows, direction)
    sweep = find_liquidity_sweep(highs, lows, closes, direction)
    pos = range_position(highs, lows, ref)
    return {
        "fvg": fvg,
        "sweep": sweep,
        "range_pos": pos,
        # SMC ekolunun tercihi: LONG iskontodan, SHORT primden
        "smc_aligned": bool(
            sweep is not None and pos is not None
            and ((direction == "LONG" and pos < 0.5)
                 or (direction == "SHORT" and pos > 0.5))),
    }
