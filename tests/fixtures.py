"""Sentetik veri ureticileri - canli API gerektirmeden engine testi (plan bolum 7)."""
from __future__ import annotations

import numpy as np

from app.models.candle import Candle, KlineSeries


def make_series(closes: np.ndarray, symbol: str = "TEST", interval: str = "1h",
                volumes: np.ndarray | None = None, spread: float = 0.004,
                seed: int = 1) -> KlineSeries:
    """Kapanis dizisinden OHLCV serisi. spread: bar ici salinim (ATR olcegi)."""
    rng = np.random.default_rng(seed)
    closes = np.asarray(closes, dtype=float)
    n = len(closes)
    high = closes * (1 + rng.uniform(spread * 0.5, spread, n))
    low = closes * (1 - rng.uniform(spread * 0.5, spread, n))
    opens = np.roll(closes, 1)
    opens[0] = closes[0]
    vols = volumes if volumes is not None else rng.uniform(900.0, 1100.0, n)
    candles = [
        Candle(ts=i * 3_600_000, open=float(opens[i]), high=float(high[i]),
               low=float(low[i]), close=float(closes[i]), volume=float(vols[i]))
        for i in range(n)
    ]
    return KlineSeries(symbol=symbol, interval=interval, candles=candles)


# ------------------------------------------------------------- gunluk seriler
def daily_uptrend_closes(n: int = 260, start: float = 50.0,
                         end: float = 100.0, wave: float = 3.0) -> np.ndarray:
    """Zigzagli yukselis: HH/HL dizilimi + close > SMA50 > SMA200."""
    trend = np.linspace(start, end, n)
    return trend + wave * np.sin(np.linspace(0, 16 * np.pi, n))


def daily_downtrend_closes(n: int = 260, start: float = 120.0,
                           end: float = 60.0, wave: float = 3.0) -> np.ndarray:
    """Zigzagli dusus: LH/LL dizilimi + close < SMA50 < SMA200."""
    trend = np.linspace(start, end, n)
    return trend + wave * np.sin(np.linspace(0, 16 * np.pi, n))


def daily_flat_closes(n: int = 260) -> np.ndarray:
    """Saf sinus: pivotlar esit -> HH/HL de LH/LL de olusmaz -> NEUTRAL."""
    return 100 + 3.0 * np.sin(np.linspace(0, 16 * np.pi, n))


def daily_neutral_index_closes(n: int = 260) -> np.ndarray:
    """Endeks NEUTRAL senaryosu: uzun dusus + SMA200 ustune sert toparlanma
    (fiyat > SMA200 ama SMA200 hala dusuyor)."""
    return np.concatenate([
        np.linspace(130.0, 95.0, n - 30),
        np.linspace(95.0, 112.0, 30),
    ])


def daily_steep_downtrend_closes(n: int = 260) -> np.ndarray:
    """Benchmark'tan da hizli dusen seri (short RS testleri icin)."""
    return daily_downtrend_closes(n, start=140.0, end=40.0, wave=3.0)


def daily_mild_downtrend_closes(n: int = 260) -> np.ndarray:
    """Endeks BEAR senaryosu / short RS kiyasi icin yumusak dusus."""
    return daily_downtrend_closes(n, start=100.0, end=85.0, wave=1.0)


# ------------------------------------------------------------- 1h setup serileri
def hourly_pullback_long_closes() -> np.ndarray:
    """Trend -> yukselen EMA20'ye sig geri cekilme (RSI3 cokusu) -> donus mumu."""
    return np.concatenate([
        np.linspace(80.0, 100.0, 100),
        np.linspace(100.0, 98.3, 8),
        [98.6, 99.2],
    ])


def hourly_pullback_short_closes() -> np.ndarray:
    """Ayna goruntusu: dusen EMA20'ye tepki yukselisi -> asagi donus mumu."""
    return np.concatenate([
        np.linspace(75.0, 62.0, 100),
        np.linspace(62.0, 63.3, 8),
        [63.0, 62.4],
    ])


def hourly_breakout_closes() -> np.ndarray:
    """Range (~128.6 tepe) -> kirilim -> acceptance -> retest -> devam."""
    return np.concatenate([
        128 + 0.6 * np.sin(np.linspace(0, 10 * np.pi, 150)),
        np.linspace(128.6, 131.5, 10),
        np.linspace(131.5, 128.8, 10),
        np.linspace(128.9, 131.0, 8),
    ])


def spike_volumes(n: int, spike_at: int = -1, mult: float = 2.0,
                  base: float = 1000.0) -> np.ndarray:
    vols = np.full(n, base)
    vols[spike_at] = base * mult
    return vols
