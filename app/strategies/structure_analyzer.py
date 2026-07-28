"""
Pipeline adim 3 ve 5: gunluk TREND + 1h SETUP tespiti (plan bolum 4).
Saf fonksiyonlar - I/O yok.

TREND (1D):
  Long : close > SMA50 > SMA200 + HH/HL
  Short: close < SMA50 < SMA200 + LH/LL   (zayif RS sarti signal_engine'de)

SETUP (1h) - oncelik sirasi:
  (a) trend_pullback : yukselen 20EMA'ya geri cekilme + RSI(3) asiriligi + donus mumu
  (b) breakout_retest: swing kirilimi + acceptance + retest
  Short'ta ayna goruntusu.

Hacim kontrolu BILINCLI olarak burada YOK: structure adayi bulur,
volume_analyzer dogrular, signal_engine karari verir (tek sorumluluk).
"""
from __future__ import annotations

import pandas as pd
from pydantic import BaseModel

from app.config.settings import StrategyParams
from app.models.decision import Bias, Direction, SetupType
from app.strategies.indicators import ema, find_pivots, rsi, sma

_RETEST_TOL = 0.002        # seviyeye %0.2 yaklasma retest sayilir
_MAX_BREAK_AGE = 40        # kirilim en fazla 40 1h bari once olmali (~1 hafta)
_MIN_ACCEPTANCE = 2        # kirilim sonrasi dogru tarafta min kapanis


class SetupCandidate(BaseModel):
    """Structure katmaninin ciktisi; hacim dogrulamasi signal_engine'de yapilir."""

    setup_type: SetupType
    level: float            # giris referans seviyesi (EMA20 veya kirilim seviyesi)
    event_index: int        # tetik mumu (hacim bu barda olculur)


class TrendResult(BaseModel):
    bias: Bias
    detail: str = ""


def classify_trend(daily: pd.DataFrame, params: StrategyParams) -> TrendResult:
    """Gunluk MA hiyerarsisi + pivot dizilimi -> BULLISH / BEARISH / NEUTRAL."""
    close = float(daily["close"].iloc[-1])
    s50 = float(sma(daily["close"], 50).iloc[-1])
    s200 = float(sma(daily["close"], 200).iloc[-1])
    ph, pl = find_pivots(daily, params.pivot_lookback, params.pivot_lookback)
    if len(ph) < 2 or len(pl) < 2:
        return TrendResult(bias=Bias.NEUTRAL, detail="pivot yetersiz")

    hh, hl = ph[-1][1] > ph[-2][1], pl[-1][1] > pl[-2][1]
    lh, ll = ph[-1][1] < ph[-2][1], pl[-1][1] < pl[-2][1]
    detail = f"close={close:.2f} sma50={s50:.2f} sma200={s200:.2f}"

    if close > s50 > s200 and hh and hl:
        return TrendResult(bias=Bias.BULLISH, detail=detail)
    if close < s50 < s200 and lh and ll:
        return TrendResult(bias=Bias.BEARISH, detail=detail)
    return TrendResult(bias=Bias.NEUTRAL, detail=detail)


def detect_pullback(hourly: pd.DataFrame, direction: Direction,
                    params: StrategyParams) -> SetupCandidate | None:
    """
    Long kosullari (hepsi zorunlu; short ayna goruntusu):
    - EMA20 yukseliyor (son deger, ema_slope_bars once ki degerden buyuk)
    - Son pullback_window bar icinde low, EMA20 bolgesine dokunmus
    - Ayni pencerede RSI(3) asiri satim bolgesine inmis
    - Son bar donus mumu: yesil, onceki kapanisin ustunde ve EMA20 ustunde
    """
    n = len(hourly)
    if n < 40:
        return None
    closes = hourly["close"]
    opens, lows, highs = hourly["open"].values, hourly["low"].values, hourly["high"].values
    e20 = ema(closes, 20)
    r3 = rsi(closes, 3)
    w = params.pullback_window
    tol = params.pullback_touch_tol
    win = range(n - w, n)

    if direction is Direction.LONG:
        if not e20.iloc[-1] > e20.iloc[-1 - params.ema_slope_bars]:
            return None
        touched = any(lows[i] <= e20.iloc[i] * (1 + tol) for i in win)
        stretched = any(r3.iloc[i] <= params.rsi3_oversold for i in win)
        c, o = float(closes.iloc[-1]), float(opens[-1])
        trigger = c > o and c > float(closes.iloc[-2]) and c > float(e20.iloc[-1])
    else:
        if not e20.iloc[-1] < e20.iloc[-1 - params.ema_slope_bars]:
            return None
        touched = any(highs[i] >= e20.iloc[i] * (1 - tol) for i in win)
        stretched = any(r3.iloc[i] >= params.rsi3_overbought for i in win)
        c, o = float(closes.iloc[-1]), float(opens[-1])
        trigger = c < o and c < float(closes.iloc[-2]) and c < float(e20.iloc[-1])

    if touched and stretched and trigger:
        return SetupCandidate(setup_type=SetupType.TREND_PULLBACK,
                              level=float(e20.iloc[-1]), event_index=n - 1)
    return None


def detect_breakout_retest(hourly: pd.DataFrame, direction: Direction,
                           params: StrategyParams) -> SetupCandidate | None:
    """
    Kosullar (hepsi zorunlu):
    - 1h swing seviyesi kirilmis ve kirilim son _MAX_BREAK_AGE bar icinde
    - Acceptance: kirilim sonrasi >= _MIN_ACCEPTANCE kapanis dogru tarafta
    - Retest: fiyat seviyeye geri dokunmus
    - Son kapanis hala seviyenin dogru tarafinda (seviye geri kaybedilmemis)
    """
    ph, pl = find_pivots(hourly, params.pivot_lookback, params.pivot_lookback)
    closes, lows, highs = hourly["close"].values, hourly["low"].values, hourly["high"].values
    n = len(hourly)
    pivots = ph if direction is Direction.LONG else pl
    candidates = [p for p in pivots if p[0] < n - 6]

    for idx, level in reversed(candidates):
        break_i: int | None = None
        for i in range(idx + 1, n - 3):
            crossed = closes[i] > level if direction is Direction.LONG else closes[i] < level
            if crossed:
                break_i = i
                break
        if break_i is None:
            continue
        if break_i < n - _MAX_BREAK_AGE:
            continue

        after = closes[break_i:n]
        accepted = (after > level) if direction is Direction.LONG else (after < level)
        if int(accepted.sum()) < _MIN_ACCEPTANCE:
            continue

        if direction is Direction.LONG:
            touched = (lows[break_i:n] <= level * (1 + _RETEST_TOL)).any()
            still_ok = closes[-1] > level
        else:
            touched = (highs[break_i:n] >= level * (1 - _RETEST_TOL)).any()
            still_ok = closes[-1] < level
        if not touched or not still_ok:
            continue

        return SetupCandidate(setup_type=SetupType.BREAKOUT_RETEST,
                              level=float(level), event_index=break_i)
    return None


def detect_setup(hourly: pd.DataFrame, direction: Direction,
                 params: StrategyParams) -> SetupCandidate | None:
    """Oncelik: trend_pullback > breakout_retest (plan bolum 4 filtre 5)."""
    return (detect_pullback(hourly, direction, params)
            or detect_breakout_retest(hourly, direction, params))
