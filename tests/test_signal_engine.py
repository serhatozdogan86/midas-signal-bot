"""Engine uctan uca testleri - sentetik veri, canli API yok (plan bolum 7)."""
from __future__ import annotations

import pytest

from app.config.settings import StrategyParams
from app.models.decision import (
    Confidence, DecisionType, Direction, EarningsInfo, MarketRegime, SetupType,
)
from app.strategies import signal_engine
from app.strategies.regime_detector import RegimeResult
from tests import fixtures as fx

P = StrategyParams()
BULL = RegimeResult(regime=MarketRegime.BULL)
BEAR = RegimeResult(regime=MarketRegime.BEAR)
NEUTRAL = RegimeResult(regime=MarketRegime.NEUTRAL)
UNKNOWN = RegimeResult(regime=MarketRegime.UNKNOWN)
E_FAR = EarningsInfo(next_date="2026-08-20", days_to=8)


def _daily(closes):
    return fx.make_series(closes, interval="1d", spread=0.02)


@pytest.fixture
def long_inputs():
    daily = _daily(fx.daily_uptrend_closes())
    hourly = fx.make_series(fx.hourly_pullback_long_closes(),
                            volumes=fx.spike_volumes(110))
    bench = _daily(fx.daily_mild_downtrend_closes()).to_dataframe()
    return daily, hourly, bench


@pytest.fixture
def short_inputs():
    daily = _daily(fx.daily_downtrend_closes())
    hourly = fx.make_series(fx.hourly_pullback_short_closes(),
                            volumes=fx.spike_volumes(110))
    bench = _daily(fx.daily_mild_downtrend_closes()).to_dataframe()
    return daily, hourly, bench


def test_long_signal_full_pipeline(long_inputs):
    daily, hourly, bench = long_inputs
    d = signal_engine.evaluate("AAPL", daily, hourly, BULL, P, bench, E_FAR)
    assert d.decision is DecisionType.SIGNAL
    assert d.direction is Direction.LONG
    assert d.setup_type is SetupType.TREND_PULLBACK
    assert d.rr is not None and d.rr >= P.min_rr
    assert d.target_pct is not None and d.target_pct >= P.min_target_pct
    assert d.stop_loss < d.entry_zone.min
    assert d.targets.tp1 < d.targets.tp2
    assert d.time_stop_days == P.time_stop_days
    assert d.gap_warning  # gap uyarisi zorunlu (plan bolum 3)
    assert d.earnings_date == "2026-08-20"
    assert d.confidence is Confidence.HIGH  # 3 confluence maddesi


def test_short_signal_bear_regime(short_inputs):
    daily, hourly, bench = short_inputs
    d = signal_engine.evaluate("XYZ", daily, hourly, BEAR, P, bench, E_FAR)
    assert d.decision is DecisionType.SIGNAL
    assert d.direction is Direction.SHORT
    assert d.stop_loss > d.entry_zone.max
    assert d.targets.tp1 > d.targets.tp2  # short'ta hedefler asagida


def test_short_requires_weak_rs(short_inputs):
    daily, hourly, _ = short_inputs
    steep_bench = _daily(fx.daily_steep_downtrend_closes()).to_dataframe()
    d = signal_engine.evaluate("XYZ", daily, hourly, BEAR, P, steep_bench, E_FAR)
    assert d.decision is DecisionType.NO_TRADE
    assert d.failed_filters == ["TREND"]


def test_bear_regime_blocks_long(long_inputs):
    daily, hourly, bench = long_inputs
    d = signal_engine.evaluate("AAPL", daily, hourly, BEAR, P, bench, E_FAR)
    assert d.decision is DecisionType.NO_TRADE
    assert d.failed_filters == ["MARKET_REGIME"]


def test_bull_regime_blocks_short(short_inputs):
    daily, hourly, bench = short_inputs
    d = signal_engine.evaluate("XYZ", daily, hourly, BULL, P, bench, E_FAR)
    assert d.decision is DecisionType.NO_TRADE
    assert d.failed_filters == ["MARKET_REGIME"]


def test_unknown_regime_no_trade(long_inputs):
    daily, hourly, bench = long_inputs
    d = signal_engine.evaluate("AAPL", daily, hourly, UNKNOWN, P, bench, E_FAR)
    assert d.decision is DecisionType.NO_TRADE
    assert d.failed_filters == ["MARKET_REGIME"]


def test_short_disabled(short_inputs):
    daily, hourly, bench = short_inputs
    params = StrategyParams(short_enabled=False)
    d = signal_engine.evaluate("XYZ", daily, hourly, BEAR, params, bench, E_FAR)
    assert d.decision is DecisionType.NO_TRADE
    assert d.failed_filters == ["MARKET_REGIME"]


def test_earnings_blackout(long_inputs):
    daily, hourly, bench = long_inputs
    near = EarningsInfo(next_date="2026-07-29", days_to=1)
    d = signal_engine.evaluate("AAPL", daily, hourly, BULL, P, bench, near)
    assert d.decision is DecisionType.NO_TRADE
    assert d.failed_filters == ["EARNINGS"]
    assert d.earnings_date == "2026-07-29"


def test_earnings_unknown_passes(long_inputs):
    """Bilanco tarihi bilinmiyorsa filtre gecer (kapsam boslugu tolere edilir)."""
    daily, hourly, bench = long_inputs
    d = signal_engine.evaluate("AAPL", daily, hourly, BULL, P, bench, EarningsInfo())
    assert d.decision is DecisionType.SIGNAL


def test_volume_fail(long_inputs):
    daily, _, bench = long_inputs
    hourly = fx.make_series(fx.hourly_pullback_long_closes(),
                            volumes=fx.spike_volumes(110, mult=1.0))
    d = signal_engine.evaluate("AAPL", daily, hourly, BULL, P, bench, E_FAR)
    assert d.decision is DecisionType.NO_TRADE
    assert d.failed_filters == ["VOLUME"]


def test_neutral_regime_tightens_volume(long_inputs):
    """1.4x hacim BULL'da yeter (1.3), NEUTRAL'da yetmez (1.3+0.2)."""
    daily, _, bench = long_inputs
    hourly = fx.make_series(fx.hourly_pullback_long_closes(),
                            volumes=fx.spike_volumes(110, mult=1.4))
    d_bull = signal_engine.evaluate("AAPL", daily, hourly, BULL, P, bench, E_FAR)
    d_neut = signal_engine.evaluate("AAPL", daily, hourly, NEUTRAL, P, bench, E_FAR)
    assert d_bull.decision is DecisionType.SIGNAL
    assert d_neut.decision is DecisionType.NO_TRADE
    assert d_neut.failed_filters == ["VOLUME"]


def test_neutral_trend_no_trade(long_inputs):
    _, hourly, bench = long_inputs
    daily = _daily(fx.daily_flat_closes())
    d = signal_engine.evaluate("AAPL", daily, hourly, BULL, P, bench, E_FAR)
    assert d.decision is DecisionType.NO_TRADE
    assert d.failed_filters == ["TREND"]


def test_cost_filter_rejects_small_target(long_inputs):
    daily, hourly, bench = long_inputs
    params = StrategyParams(min_target_pct=10.0)  # ulasilmaz esik
    d = signal_engine.evaluate("AAPL", daily, hourly, BULL, params, bench, E_FAR)
    assert d.decision is DecisionType.NO_TRADE
    assert d.failed_filters == ["RISK_REWARD"]
    assert "maliyet" in d.reject_reason


def test_data_missing(long_inputs):
    daily, _, _ = long_inputs
    d = signal_engine.evaluate("AAPL", daily, None, BULL, P)
    assert d.decision is DecisionType.DATA_MISSING
    assert d.data_missing == ["hourly_klines"]
    assert d.failed_filters == ["DATA"]


# ------------------------------------------- iki gecisli tarama sozlesmesi
def test_pass1_no_hourly_fails_at_trend_not_data(long_inputs):
    """1. gecis (hourly=None): trend'de elenen sembol DATA_MISSING DEGIL
    NO_TRADE/TREND almali - gunluk filtreler 1h verisiz kosulabilmeli."""
    _, _, bench = long_inputs
    daily = _daily(fx.daily_flat_closes())
    d = signal_engine.evaluate("AAPL", daily, None, BULL, P, bench, E_FAR)
    assert d.decision is DecisionType.NO_TRADE
    assert d.failed_filters == ["TREND"]


def test_pass1_survivor_flags_hourly_missing(long_inputs):
    """1. gecis: gunluk filtrelerden gecen sembol 1h aday olarak isaretlenir."""
    daily, _, bench = long_inputs
    d = signal_engine.evaluate("AAPL", daily, None, BULL, P, bench, E_FAR)
    assert d.decision is DecisionType.DATA_MISSING
    assert d.data_missing == ["hourly_klines"]
