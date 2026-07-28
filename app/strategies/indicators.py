"""
Saf indikator hesaplari - I/O yok, yan etki yok, deterministik.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

Pivot = tuple[int, float]  # (bar index, fiyat)


def sma(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(n).mean()


def ema(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(span=n, adjust=False).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift()).abs()
    lc = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def find_pivots(df: pd.DataFrame, left: int = 3, right: int = 3) -> tuple[list[Pivot], list[Pivot]]:
    """
    Fractal swing high/low pivotlari (kronolojik).
    Son 'right' bar teyitsiz oldugundan pivot sayilmaz -> repaint yok.
    """
    highs: list[Pivot] = []
    lows: list[Pivot] = []
    h, l = df["high"].values, df["low"].values
    for i in range(left, len(df) - right):
        if h[i] == max(h[i - left:i + right + 1]):
            highs.append((i, float(h[i])))
        if l[i] == min(l[i - left:i + right + 1]):
            lows.append((i, float(l[i])))
    return highs, lows
