"""YFinanceClient testleri."""
from __future__ import annotations

from app.integrations.yfinance_client import YFinanceClient


def test_dot_class_symbols_translated_to_yahoo(monkeypatch):
    """BRK.B -> BRK-B cevirisi ve sonucta orijinal isme geri esleme."""
    client = YFinanceClient(chunk_size=10, chunk_pause_sec=0)
    seen = {}

    def fake_download(chunk, **kw):
        seen["chunk"] = list(chunk)
        import pandas as pd
        idx = pd.date_range("2026-07-01", periods=3, freq="D", tz="UTC")
        cols = pd.MultiIndex.from_product(
            [chunk, ["Open", "High", "Low", "Close", "Volume"]])
        df = pd.DataFrame(1.0, index=idx, columns=cols)
        return df

    import yfinance as yf
    monkeypatch.setattr(yf, "download", fake_download)
    out = client.download_bulk(["BRK.B", "AAPL"], "1d", "1mo")
    assert seen["chunk"] == ["BRK-B", "AAPL"]      # Yahoo bicimiyle istendi
    assert "BRK.B" in out and "AAPL" in out        # orijinal adla dondu
