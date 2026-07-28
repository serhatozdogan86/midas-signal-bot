"""NYSE takvim testleri - statik tatil tablosu."""
from __future__ import annotations

from datetime import date, time

from app.services.market_calendar import MarketCalendar

CAL = MarketCalendar()


def test_weekend_not_trading():
    assert not CAL.is_trading_day(date(2026, 7, 25))  # cumartesi
    assert not CAL.is_trading_day(date(2026, 7, 26))  # pazar


def test_holiday_not_trading():
    assert not CAL.is_trading_day(date(2026, 7, 3))    # 4 Temmuz (gozlenen)
    assert not CAL.is_trading_day(date(2026, 11, 26))  # Sukran Gunu


def test_regular_day_session_times():
    times = CAL.session_times(date(2026, 7, 28))
    assert times is not None
    open_dt, close_dt = times
    assert (open_dt.hour, open_dt.minute) == (9, 30)
    assert (close_dt.hour, close_dt.minute) == (16, 0)


def test_early_close():
    times = CAL.session_times(date(2026, 11, 27))  # Sukran ertesi
    assert times is not None
    assert times[1].time() == time(13, 0)


def test_add_trading_days_skips_holiday_and_weekend():
    # 1 Tem Car -> +2: 2 Tem Per, sonra 3 Tem tatil + haftasonu -> 6 Tem Pzt
    assert CAL.add_trading_days(date(2026, 7, 1), 2) == date(2026, 7, 6)


def test_trading_days_between_signed():
    assert CAL.trading_days_between(date(2026, 7, 1), date(2026, 7, 7)) == 3
    assert CAL.trading_days_between(date(2026, 7, 7), date(2026, 7, 1)) == -3
    assert CAL.trading_days_between(date(2026, 7, 1), date(2026, 7, 1)) == 0
