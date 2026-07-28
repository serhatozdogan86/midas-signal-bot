"""
Confluence girdileri (plan bolum 4 madde 7 - filtre DEGIL):
- RS: hissenin SPY'a gore N gunluk getiri farki
- 52 haftalik zirveye / dibe yakinlik
Sektor ETF eslesmesi Phase 4'te zenginlestirilecek (plan bolum 7).
Saf fonksiyonlar - I/O yok.
"""
from __future__ import annotations

import pandas as pd

from app.config.settings import StrategyParams
from app.models.decision import Direction

_52W_BARS = 252


def rs_score(stock_close: pd.Series, bench_close: pd.Series,
             lookback: int = 63) -> float | None:
    """Getiri farki (yuzde puan). Pozitif -> hisse endeksten guclu."""
    if len(stock_close) <= lookback or len(bench_close) <= lookback:
        return None
    s0, s1 = float(stock_close.iloc[-1 - lookback]), float(stock_close.iloc[-1])
    b0, b1 = float(bench_close.iloc[-1 - lookback]), float(bench_close.iloc[-1])
    if s0 <= 0 or b0 <= 0:
        return None
    return round((s1 / s0 - 1) * 100 - (b1 / b0 - 1) * 100, 2)


def high_52w_distance_pct(daily: pd.DataFrame) -> float | None:
    """Kapanisin 52H zirvesine uzakligi (%, negatif = zirvenin altinda)."""
    if len(daily) < 60:
        return None
    window = daily["high"].iloc[-_52W_BARS:]
    hi = float(window.max())
    close = float(daily["close"].iloc[-1])
    return round((close / hi - 1) * 100, 2) if hi > 0 else None


def low_52w_distance_pct(daily: pd.DataFrame) -> float | None:
    """Kapanisin 52H dibine uzakligi (%, pozitif = dibin ustunde)."""
    if len(daily) < 60:
        return None
    window = daily["low"].iloc[-_52W_BARS:]
    lo = float(window.min())
    close = float(daily["close"].iloc[-1])
    return round((close / lo - 1) * 100, 2) if lo > 0 else None


def collect_confluence(daily: pd.DataFrame, bench_daily: pd.DataFrame | None,
                       direction: Direction, vol_ratio: float,
                       params: StrategyParams) -> list[str]:
    """Karari degistirmez; confidence derecesini besler (plan bolum 4)."""
    items: list[str] = []
    rs = (rs_score(daily["close"], bench_daily["close"], params.rs_lookback_days)
          if bench_daily is not None else None)

    if direction is Direction.LONG:
        if rs is not None and rs > 0:
            items.append(f"RS({params.rs_lookback_days}g) SPY ustunde (+{rs:.1f}pp)")
        dist = high_52w_distance_pct(daily)
        if dist is not None and dist >= -params.near_high_pct:
            items.append(f"52H zirvesine yakin ({dist:+.1f}%)")
    else:
        if rs is not None and rs < 0:
            items.append(f"RS({params.rs_lookback_days}g) SPY altinda ({rs:.1f}pp)")
        dist = low_52w_distance_pct(daily)
        if dist is not None and dist <= params.near_high_pct:
            items.append(f"52H dibine yakin ({dist:+.1f}%)")

    if vol_ratio >= 2.0:
        items.append(f"guclu katilim ({vol_ratio:.1f}x hacim)")
    return items
