"""Evren testleri: Midas HTML parser (offline fixture) + likidite filtresi."""
from __future__ import annotations

import numpy as np

from app.config.settings import Settings
from app.services.universe import UniverseProvider, parse_midas_html
from tests import fixtures as fx

_HTML = """
<html><body><table>
<tr><td><a href="/amerikan-borsasi/aapl-hisse-canli">Apple</a></td></tr>
<tr><td><a href="/amerikan-borsasi/msft-hisse">Microsoft</a></td></tr>
<tr><td><a href="/amerikan-borsasi/brk-b-hisse">Berkshire</a></td></tr>
<tr><td><a href="/blog/abd-hisse-rehberi">rehber</a></td></tr>
</table></body></html>
"""


def test_parse_midas_html_extracts_tickers():
    symbols = parse_midas_html(_HTML)
    assert "AAPL" in symbols and "MSFT" in symbols
    assert "BRK.B" in symbols          # slug tire -> nokta donusumu
    assert "REHBERI" not in symbols    # hisse olmayan slug elenir


class FakeMarketData:
    """Likidite filtresi icin sabit gunluk seriler."""

    def __init__(self):
        big = fx.make_series(np.full(30, 100.0), interval="1d",
                             volumes=np.full(30, 1_000_000.0))       # 100M$/gun
        cheap = fx.make_series(np.full(30, 2.0), interval="1d",
                               volumes=np.full(30, 10_000_000.0))    # fiyat < 3$
        thin = fx.make_series(np.full(30, 50.0), interval="1d",
                              volumes=np.full(30, 1_000.0))          # 50K$/gun
        self._data = {"BIG": big, "CHEAP": cheap, "THIN": thin}

    def get_daily_bulk(self, symbols, period=None):
        return {s: self._data[s] for s in symbols if s in self._data}


def test_liquidity_filter(tmp_path):
    static = tmp_path / "static.txt"
    static.write_text("BIG\nCHEAP\nTHIN\nMISSING\n")
    settings = Settings(UNIVERSE_SOURCE="static",
                        STATIC_UNIVERSE_PATH=str(static),
                        UNIVERSE_CACHE_PATH=str(tmp_path / "cache.json"),
                        UNIVERSE_MIN_PRICE=3.0,
                        UNIVERSE_MIN_DOLLAR_VOL=5_000_000)
    provider = UniverseProvider(settings, FakeMarketData())
    symbols = provider.refresh(force=True)
    assert symbols == ["BIG"]   # fiyat, dolar hacmi ve veri filtreleri
    assert provider.describe()["filtered_count"] == 1
