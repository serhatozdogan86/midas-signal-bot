"""Gunluk trend + 1h setup tespiti testleri."""
from __future__ import annotations

from app.config.settings import StrategyParams
from app.models.decision import Bias, Direction, SetupType
from app.strategies import structure_analyzer as sa
from tests import fixtures as fx

P = StrategyParams()


def _daily(closes):
    return fx.make_series(closes, interval="1d", spread=0.02).to_dataframe()


def test_trend_bullish():
    assert sa.classify_trend(_daily(fx.daily_uptrend_closes()), P).bias is Bias.BULLISH


def test_trend_bearish():
    assert sa.classify_trend(_daily(fx.daily_downtrend_closes()), P).bias is Bias.BEARISH


def test_trend_neutral_sideways():
    assert sa.classify_trend(_daily(fx.daily_flat_closes()), P).bias is Bias.NEUTRAL


def test_pullback_long_detected():
    hourly = fx.make_series(fx.hourly_pullback_long_closes()).to_dataframe()
    s = sa.detect_pullback(hourly, Direction.LONG, P)
    assert s is not None and s.setup_type is SetupType.TREND_PULLBACK
    assert s.event_index == len(hourly) - 1  # tetik = son bar


def test_pullback_short_detected():
    hourly = fx.make_series(fx.hourly_pullback_short_closes()).to_dataframe()
    s = sa.detect_pullback(hourly, Direction.SHORT, P)
    assert s is not None and s.setup_type is SetupType.TREND_PULLBACK


def test_pullback_wrong_direction_none():
    hourly = fx.make_series(fx.hourly_pullback_long_closes()).to_dataframe()
    assert sa.detect_pullback(hourly, Direction.SHORT, P) is None


def test_breakout_retest_detected():
    hourly = fx.make_series(fx.hourly_breakout_closes()).to_dataframe()
    s = sa.detect_breakout_retest(hourly, Direction.LONG, P)
    assert s is not None and s.setup_type is SetupType.BREAKOUT_RETEST
    assert 128.0 < s.level < 130.0


def test_detect_setup_priority_pullback_first():
    hourly = fx.make_series(fx.hourly_pullback_long_closes()).to_dataframe()
    s = sa.detect_setup(hourly, Direction.LONG, P)
    assert s is not None and s.setup_type is SetupType.TREND_PULLBACK
