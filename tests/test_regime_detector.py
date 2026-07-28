"""Endeks rejim tespiti testleri (SPY/QQQ bilesimi)."""
from __future__ import annotations

from app.models.decision import MarketRegime
from app.strategies import regime_detector as rd
from tests import fixtures as fx


def _daily(closes):
    return fx.make_series(closes, interval="1d", spread=0.02).to_dataframe()


UP = _daily(fx.daily_uptrend_closes())
DOWN = _daily(fx.daily_mild_downtrend_closes())
MIXED = _daily(fx.daily_neutral_index_closes())


def test_index_bull():
    assert rd.classify_index(UP) == "bull"


def test_index_bear():
    assert rd.classify_index(DOWN) == "bear"


def test_index_neutral():
    # fiyat SMA200 ustunde ama SMA200 hala dusuyor -> teyitsiz
    assert rd.classify_index(MIXED) == "neutral"


def test_index_unknown_short_series():
    short = _daily(fx.daily_uptrend_closes(n=100))
    assert rd.classify_index(short) == "unknown"


def test_market_regime_bull():
    assert rd.classify_market_regime(UP, UP).regime is MarketRegime.BULL


def test_market_regime_bear():
    assert rd.classify_market_regime(DOWN, DOWN).regime is MarketRegime.BEAR


def test_market_regime_neutral_on_disagreement():
    assert rd.classify_market_regime(UP, DOWN).regime is MarketRegime.NEUTRAL


def test_market_regime_unknown_on_missing():
    assert rd.classify_market_regime(None, UP).regime is MarketRegime.UNKNOWN
