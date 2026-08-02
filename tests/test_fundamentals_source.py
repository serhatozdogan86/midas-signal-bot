"""v3.9.1: fundamentals kaynak devri (Finnhub birincil / yfinance yedek).

Kok neden: Yahoo .info ucu Render'in veri merkezi IP'sinde engelli
(yerelde 183 alan doner, Render'da 5/5 basarisiz). Bu testler kaynak
secim mantigini ve kismi veri toleransini kilitler.
"""
from __future__ import annotations

from app.services.fundamentals_service import FundamentalsService


class FakeFinnhub:
    """configured=True; profile2 ve metric davranisi test basina ayarlanir."""

    def __init__(self, profile=None, metric=None, raise_on=None):
        self.configured = True
        self._profile = profile
        self._metric = metric
        self._raise_on = raise_on or set()
        self.calls: list[str] = []

    def get_company_profile(self, symbol):
        self.calls.append("profile")
        if "profile" in self._raise_on:
            raise RuntimeError("boom")
        return self._profile

    def get_basic_financials(self, symbol):
        self.calls.append("metric")
        if "metric" in self._raise_on:
            raise RuntimeError("boom")
        return self._metric


_PROFILE = {"finnhubIndustry": "Utilities", "marketCapitalization": 32000.0,
            "name": "PG&E"}
_METRIC = {"peTTM": 12.5, "pbQuarterly": 1.4,
           "totalDebt/totalEquityQuarterly": 2.10, "ebitdaMarginTTM": 31.44}


def test_finnhub_primary_full_data():
    svc = FundamentalsService(finnhub=FakeFinnhub(_PROFILE, _METRIC))
    out = svc.get_many(["PCG"])
    assert out["PCG"]["sector"] == "Utilities"
    assert out["PCG"]["pe"] == 12.5
    assert out["PCG"]["price_to_book"] == 1.4
    # BIRIM SOZLESMESI: dashboard yuzde basar; Finnhub oran verir -> x100
    assert out["PCG"]["debt_to_equity"] == 210.0
    assert out["PCG"]["ebitda_margin"] == 31.4
    # Finnhub milyon $ verir -> mutlak $'a cevrilmeli
    assert out["PCG"]["market_cap"] == 32000.0 * 1e6
    assert svc.last_source.get("finnhub") == 1


def test_finnhub_partial_when_metric_restricted():
    """Ucretsiz planda /stock/metric kisitliysa (None) sektor+piyasa
    degeri yine gelir; oranlar None kalir - kismi veri > hic veri."""
    svc = FundamentalsService(finnhub=FakeFinnhub(_PROFILE, None))
    out = svc.get_many(["PCG"])
    assert out["PCG"]["sector"] == "Utilities"
    assert out["PCG"]["pe"] is None and out["PCG"]["price_to_book"] is None
    assert out["PCG"]["market_cap"] == 32000.0 * 1e6


def test_metric_exception_does_not_kill_profile():
    svc = FundamentalsService(finnhub=FakeFinnhub(_PROFILE, None,
                                                  raise_on={"metric"}))
    out = svc.get_many(["PCG"])
    assert out["PCG"]["sector"] == "Utilities"


def test_falls_back_to_yfinance_when_finnhub_empty(monkeypatch):
    svc = FundamentalsService(finnhub=FakeFinnhub(None, None))
    monkeypatch.setattr(FundamentalsService, "_from_yfinance",
                        staticmethod(lambda s: {"sector": "Tech", "pe": 30.0}))
    out = svc.get_many(["AAPL"])
    assert out["AAPL"]["sector"] == "Tech"
    assert svc.last_source.get("yfinance") == 1
    assert svc.last_source.get("finnhub") is None


def test_unconfigured_finnhub_skips_to_yfinance(monkeypatch):
    fake = FakeFinnhub(_PROFILE, _METRIC)
    fake.configured = False
    svc = FundamentalsService(finnhub=fake)
    monkeypatch.setattr(FundamentalsService, "_from_yfinance",
                        staticmethod(lambda s: {"sector": "Tech"}))
    svc.get_many(["AAPL"])
    assert fake.calls == []          # anahtar yoksa Finnhub'a hic gidilmez


def test_profile_exception_falls_back(monkeypatch):
    svc = FundamentalsService(finnhub=FakeFinnhub(raise_on={"profile"}))
    monkeypatch.setattr(FundamentalsService, "_from_yfinance",
                        staticmethod(lambda s: {"sector": "Tech"}))
    out = svc.get_many(["AAPL"])
    assert out["AAPL"]["sector"] == "Tech"


def test_total_failure_is_silent_and_symbol_absent(monkeypatch):
    svc = FundamentalsService(finnhub=FakeFinnhub(None, None))
    monkeypatch.setattr(FundamentalsService, "_from_yfinance",
                        staticmethod(lambda s: None))
    assert svc.get_many(["AAPL", "MSFT"]) == {}   # dashboard '-' gosterir


def test_cache_prevents_second_fetch():
    fake = FakeFinnhub(_PROFILE, _METRIC)
    svc = FundamentalsService(finnhub=fake)
    svc.get_many(["PCG"])
    n = len(fake.calls)
    svc.get_many(["PCG"])
    assert len(fake.calls) == n      # 24 saat onbellek


def test_debt_to_equity_unit_is_percent_not_ratio():
    """REGRESYON: Finnhub oran (2.06) verir, dashboard yuzde basar.
    Cevrilmezse GM icin '%2' yazardi - gercek deger %206."""
    svc = FundamentalsService(finnhub=FakeFinnhub(
        _PROFILE, {"totalDebt/totalEquityQuarterly": 2.0596}))
    assert svc.get_many(["GM"])["GM"]["debt_to_equity"] == 206.0
