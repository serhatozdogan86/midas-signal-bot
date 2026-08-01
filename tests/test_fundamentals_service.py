"""FundamentalsService testleri."""
from __future__ import annotations

from app.services.fundamentals_service import FundamentalsService


class _FakeTicker:
    def __init__(self, symbol):
        self.symbol = symbol

    @property
    def info(self):
        if self.symbol == "BAD":
            raise RuntimeError("network kapali")
        if self.symbol == "ETF":
            return {"sector": None}          # ETF gibi - sektor yok -> None
        return {
            "sector": "Utilities", "industry": "Diversified Utilities",
            "trailingPE": 18.4, "marketCap": 3_200_000_000,
            "priceToBook": 1.35, "debtToEquity": 92.1,
            "ebitdaMargins": 0.317,
        }


def test_get_many_maps_fields_and_formats_ebitda(monkeypatch):
    import yfinance as yf
    monkeypatch.setattr(yf, "Ticker", _FakeTicker)
    svc = FundamentalsService()
    out = svc.get_many(["PCG"])
    assert out["PCG"]["sector"] == "Utilities"
    assert out["PCG"]["pe"] == 18.4
    assert out["PCG"]["price_to_book"] == 1.35
    assert out["PCG"]["ebitda_margin"] == 31.7      # 0.317 -> yuzde


def test_get_many_skips_failed_and_sectorless_symbols(monkeypatch):
    import yfinance as yf
    monkeypatch.setattr(yf, "Ticker", _FakeTicker)
    svc = FundamentalsService()
    out = svc.get_many(["PCG", "BAD", "ETF"])
    assert "PCG" in out
    assert "BAD" not in out
    assert "ETF" not in out


def test_get_many_caches_within_ttl(monkeypatch):
    import yfinance as yf
    calls = {"n": 0}

    class CountingTicker(_FakeTicker):
        @property
        def info(self):
            calls["n"] += 1
            return super().info

    monkeypatch.setattr(yf, "Ticker", CountingTicker)
    svc = FundamentalsService(ttl_sec=999)
    svc.get_many(["PCG"])
    svc.get_many(["PCG"])
    assert calls["n"] == 1                          # ikinci cagri onbellekten
