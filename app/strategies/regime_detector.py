"""
Pipeline adim 2: MARKET_REGIME - endeks bazli rejim (plan bolum 4 filtre 2).
SPY & QQQ gunluk: 200G SMA konumu + egimi -> BULL / BEAR / NEUTRAL.
Saf fonksiyon; endeks DataFrame'leri disaridan verilir.
"""
from __future__ import annotations

import pandas as pd
from pydantic import BaseModel

from app.models.decision import MarketRegime
from app.strategies.indicators import sma

_MIN_BARS = 210
_SLOPE_BARS = 21  # SMA200 egimi ~1 ay onceyle kiyaslanir


class RegimeResult(BaseModel):
    regime: MarketRegime
    detail: str = ""


def classify_index(df: pd.DataFrame | None) -> str:
    """Tek endeks durumu: 'bull' | 'bear' | 'neutral' | 'unknown'."""
    if df is None or len(df) < _MIN_BARS:
        return "unknown"
    close = float(df["close"].iloc[-1])
    s200 = sma(df["close"], 200)
    last = float(s200.iloc[-1])
    prev = float(s200.iloc[-1 - _SLOPE_BARS])
    rising, falling = last > prev, last < prev
    if close > last and rising:
        return "bull"
    if close < last and falling:
        return "bear"
    return "neutral"


def classify_market_regime(spy: pd.DataFrame | None,
                           qqq: pd.DataFrame | None) -> RegimeResult:
    """
    Iki endeksin bilesimi:
      ikisi de bull -> BULL, ikisi de bear -> BEAR,
      herhangi biri unknown -> UNKNOWN (guvenli taraf: sinyal uretilmez),
      aksi -> NEUTRAL (esikler sikilasir).
    """
    a, b = classify_index(spy), classify_index(qqq)
    detail = f"SPY={a} QQQ={b}"
    if "unknown" in (a, b):
        return RegimeResult(regime=MarketRegime.UNKNOWN, detail=detail)
    if a == b == "bull":
        return RegimeResult(regime=MarketRegime.BULL, detail=detail)
    if a == b == "bear":
        return RegimeResult(regime=MarketRegime.BEAR, detail=detail)
    return RegimeResult(regime=MarketRegime.NEUTRAL, detail=detail)
