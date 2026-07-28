"""EarningsService testleri - sahte Finnhub istemcisiyle."""
from __future__ import annotations

from datetime import date

from app.services.earnings_service import EarningsService
from app.services.market_calendar import MarketCalendar


class FakeFinnhub:
    def __init__(self, rows):
        self._rows = rows
        self.calls = 0

    def get_earnings_calendar(self, date_from, date_to):
        self.calls += 1
        return self._rows


def test_info_returns_signed_trading_day_distance():
    fake = FakeFinnhub([
        {"symbol": "AAPL", "date": "2026-08-04"},
        {"symbol": "MSFT", "date": "2026-07-27"},   # gecmis (dun)
    ])
    svc = EarningsService(fake, MarketCalendar())
    today = date(2026, 7, 28)
    svc.refresh(today, force=True)

    aapl = svc.info("AAPL", today)
    assert aapl.next_date == "2026-08-04"
    assert aapl.days_to == 5   # 29,30,31 Tem + 3,4 Agu

    msft = svc.info("MSFT", today)
    assert msft.days_to == -1  # dun acikladi -> blackout kapsaminda


def test_unknown_symbol_empty_info():
    svc = EarningsService(FakeFinnhub([]), MarketCalendar())
    info = svc.info("NVDA", date(2026, 7, 28))
    assert info.next_date is None and info.days_to is None


def test_cache_ttl_prevents_refetch():
    fake = FakeFinnhub([{"symbol": "AAPL", "date": "2026-08-04"}])
    svc = EarningsService(fake, MarketCalendar())
    today = date(2026, 7, 28)
    svc.refresh(today, force=True)
    svc.refresh(today)  # TTL icinde -> yeni cagri yok
    assert fake.calls == 1
