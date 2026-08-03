"""v3.15 SMC etiketleri: yalnizca METADATA.

En kritik test sonuncusu: signal_engine bu modulu import ETMEMELI -
etiketlerin karara sizmadigi kod duzeyinde guvence altina alinir.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.strategies.smc_tags import (find_fvg, find_liquidity_sweep,
                                     range_position, tag_candles)


def _c(o, h, low, cl):
    return SimpleNamespace(open=o, high=h, low=low, close=cl)


# ------------------------------------------------------------- FVG
def test_bullish_fvg_detected():
    # i-2 tepesi 101, i dibi 103 -> arada doldurulmamis boslik
    highs = [100, 101, 102, 105, 106]
    lows = [99, 100, 101, 103, 104]
    fvg = find_fvg(highs, lows, "LONG")
    assert fvg is not None and fvg["size"] == 2.0


def test_no_fvg_when_candles_overlap():
    # mumlar ortusuyor: her i icin low[i] <= high[i-2]
    highs = [100, 101, 102, 103, 104]
    lows = [95, 96, 97, 98, 99]
    assert find_fvg(highs, lows, "LONG") is None


def test_bearish_fvg_mirror():
    highs = [110, 109, 108, 105, 104]
    lows = [109, 108, 107, 104, 103]
    fvg = find_fvg(highs, lows, "SHORT")
    assert fvg is not None and fvg["size"] == 3.0
    # ayni seri LONG icin boga FVG'si vermemeli
    assert find_fvg(highs, lows, "LONG") is None


# -------------------------------------------------- likidite avi
def _sweep_series():
    """Swing dip 6. barda 95; 14. barda 93'e DELINIP 15. barda 97
    kapanisiyla geri kazaniliyor (klasik stop avi)."""
    lows = [100, 99, 98, 97, 96.5, 96, 95, 96, 97, 98,
            99, 98, 97, 96, 93, 96, 97, 98, 99, 100]
    highs = [x + 2 for x in lows]
    closes = [100.5, 99.5, 98.5, 97.5, 97, 96.5, 95.5, 96.5, 97.5, 98.5,
              99.5, 98.5, 97.5, 96.5, 94, 97, 97.5, 98.5, 99.5, 100.5]
    return highs, lows, closes


def test_liquidity_sweep_detected_for_long():
    h, low, c = _sweep_series()
    sw = find_liquidity_sweep(h, low, c, "LONG")
    assert sw is not None and sw["level"] == 95.0


def test_no_sweep_when_level_not_reclaimed():
    h, low, c = _sweep_series()
    # delinme sonrasi kapanislar seviyenin ALTINDA kalir
    c = c[:14] + [94.0, 94.2, 94.1, 93.8, 93.5, 93.2]
    low = low[:14] + [93.0, 93.2, 93.1, 92.9, 92.7, 92.5]
    assert find_liquidity_sweep(h, low, c, "LONG") is None


def test_sweep_needs_enough_bars():
    assert find_liquidity_sweep([1, 2], [1, 2], [1, 2], "LONG") is None


# ------------------------------------------- prim / iskonto konumu
def test_range_position_discount_and_premium():
    highs = [110] * 10
    lows = [100] * 10
    assert range_position(highs, lows, 102) == 0.2       # iskonto
    assert range_position(highs, lows, 108) == 0.8       # prim
    assert range_position(highs, lows, 105) == 0.5


def test_range_position_flat_range_is_none():
    assert range_position([100] * 5, [100] * 5, 100) is None


# --------------------------------------------------- tag_candles
def test_tag_candles_shape_and_alignment():
    h, low, c = _sweep_series()
    candles = [_c(x, x, y, z) for x, y, z in zip(h, low, c)]
    tags = tag_candles(candles, "LONG", entry=95.5)
    assert set(tags) == {"fvg", "sweep", "range_pos", "smc_aligned"}
    assert tags["sweep"] is not None
    # giris iskontoda + avi var -> SMC ekolune gore hizali
    assert tags["smc_aligned"] is True


def test_tag_candles_short_series_returns_empty():
    assert tag_candles([_c(1, 1, 1, 1)] * 3, "LONG") == {}


def test_tag_candles_survives_bad_input():
    assert tag_candles([SimpleNamespace(high="x")], "LONG") == {}


# ----------------------------------------------------------------
def test_smc_never_influences_decisions():
    """GUVENCE: etiketler yalnizca kayittir. Karar veren modullerin
    hicbiri smc_tags'i import etmemeli."""
    from pathlib import Path
    for mod in ("signal_engine.py", "structure_analyzer.py",
                "risk_manager.py", "regime_detector.py", "session_guard.py"):
        src = Path("app/strategies") / mod
        if src.exists():
            assert "smc_tags" not in src.read_text(), mod
