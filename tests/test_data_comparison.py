"""Asama 0 testleri: Alpaca istemcisi + yfinance karsilastirmasi (salt gozlem)."""
from __future__ import annotations

import pandas as pd

from app.integrations.alpaca_client import AlpacaClient
from app.services.data_comparison import DataComparisonService


def _frame(closes, start="2026-07-01", freq="D"):
    idx = pd.date_range(start, periods=len(closes), freq=freq, tz="UTC")
    return pd.DataFrame({
        "Open": closes, "High": [c + 1 for c in closes],
        "Low": [c - 1 for c in closes], "Close": closes,
        "Volume": [1_000_000] * len(closes),
    }, index=idx)


class FakeSource:
    def __init__(self, frames):
        self.frames = frames
        self.enabled = True

    def download_bulk(self, symbols, interval, *args, **kwargs):
        return {s: f for s, f in self.frames.items() if s in symbols}


def test_disabled_without_credentials():
    """Anahtar yoksa istemci ve karsilastirma tamamen devre disi."""
    client = AlpacaClient("", "")
    assert client.enabled is False
    assert client.download_bulk(["AAPL"], "1d") == {}
    svc = DataComparisonService(FakeSource({}), client)
    assert svc.enabled is False
    assert svc.compare(["AAPL"]) is None


def test_alpaca_frame_conversion_matches_yfinance_shape():
    """Alpaca bar sozlugu -> YFinanceClient ile AYNI kolon/indeks sekli."""
    bars = [
        {"t": "2026-07-01T00:00:00Z", "o": 10, "h": 11, "l": 9, "c": 10.5, "v": 500},
        {"t": "2026-07-02T00:00:00Z", "o": 10.5, "h": 12, "l": 10, "c": 11.5, "v": 700},
    ]
    df = AlpacaClient._to_frame(bars)
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(df) == 2
    assert df["Close"].iloc[-1] == 11.5
    assert str(df.index.tz) == "UTC"
    assert AlpacaClient._to_frame([]) is None


def test_comparison_detects_agreement():
    """Iki kaynak ayni veriyi verdiginde sapma ~0 ve uyusmazlik yok."""
    frames = {"AAPL": _frame([100, 101, 102, 103]),
              "MSFT": _frame([200, 201, 202, 203])}
    svc = DataComparisonService(FakeSource(frames), FakeSource(dict(frames)))
    rep = svc.compare(["AAPL", "MSFT"])
    assert rep["compared"] == 2
    assert rep["median_dev_pct"] == 0.0
    assert rep["mismatch_count"] == 0
    assert rep["yf_only"] == [] and rep["alpaca_only"] == []


def test_comparison_flags_price_mismatch_and_coverage_gap():
    """Sapma esigi asilirsa uyusmazlik; sembol eksikse kapsam farki raporlanir."""
    yf = FakeSource({"AAPL": _frame([100, 101, 102, 103]),
                     "BRK.B": _frame([300, 301, 302, 303])})
    # AAPL'de son KAPALI bar (sondan ikinci) farkli: 102 -> 108 (%5.9)
    alpaca = FakeSource({"AAPL": _frame([100, 101, 108, 103])})
    svc = DataComparisonService(yf, alpaca)
    rep = svc.compare(["AAPL", "BRK.B"])
    assert rep["mismatch_count"] == 1
    assert rep["mismatches"][0]["symbol"] == "AAPL"
    assert rep["mismatches"][0]["pct"] > 5
    assert rep["yf_only"] == ["BRK.B"]        # Alpaca'da yok
    assert "BRK.B" in svc.summary_line()


def test_last_bar_excluded_from_comparison():
    """Olusmakta olan SON bar karsilastirilmaz (ucretsiz plan 15dk kisiti):
    sadece son barda fark varsa uyusmazlik sayilmamali."""
    yf = FakeSource({"AAPL": _frame([100, 101, 102, 103])})
    alpaca = FakeSource({"AAPL": _frame([100, 101, 102, 999])})
    svc = DataComparisonService(yf, alpaca)
    rep = svc.compare(["AAPL"])
    assert rep["mismatch_count"] == 0
    assert rep["median_dev_pct"] == 0.0


def test_summary_line_empty_before_first_run():
    svc = DataComparisonService(FakeSource({}), FakeSource({}))
    assert svc.summary_line() == ""
