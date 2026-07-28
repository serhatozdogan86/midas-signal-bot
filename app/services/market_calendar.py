"""
NYSE seans/tatil takvimi - statik liste yaklasimi (plan bolum 3).
pandas_market_calendars bagimliligi yerine 2025-2027 tatilleri gomulu tutulur;
tablo disina cikilirsa WARNING loglanir (yillik bakim notu README'de).
Saf/deterministik: 'now' her fonksiyona enjekte edilebilir.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.logging_setup import kv

log = logging.getLogger("calendar")

ET = ZoneInfo("America/New_York")

_OPEN = time(9, 30)
_CLOSE = time(16, 0)
_EARLY_CLOSE = time(13, 0)

# Tam gun tatiller (NYSE)
NYSE_HOLIDAYS: set[date] = {
    # 2025
    date(2025, 1, 1), date(2025, 1, 20), date(2025, 2, 17), date(2025, 4, 18),
    date(2025, 5, 26), date(2025, 6, 19), date(2025, 7, 4), date(2025, 9, 1),
    date(2025, 11, 27), date(2025, 12, 25),
    # 2026
    date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3),
    date(2026, 5, 25), date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7),
    date(2026, 11, 26), date(2026, 12, 25),
    # 2027
    date(2027, 1, 1), date(2027, 1, 18), date(2027, 2, 15), date(2027, 3, 26),
    date(2027, 5, 31), date(2027, 6, 18), date(2027, 7, 5), date(2027, 9, 6),
    date(2027, 11, 25), date(2027, 12, 24),
}

# Erken kapanis gunleri (13:00 ET)
NYSE_EARLY_CLOSE: set[date] = {
    date(2025, 7, 3), date(2025, 11, 28), date(2025, 12, 24),
    date(2026, 11, 27), date(2026, 12, 24),
    date(2027, 11, 26),
}

_TABLE_MAX_YEAR = 2027


class MarketCalendar:
    """NYSE seans sorgulari. Tum datetime'lar America/New_York dilimindedir."""

    def now_et(self) -> datetime:
        return datetime.now(ET)

    def is_trading_day(self, d: date) -> bool:
        if d.year > _TABLE_MAX_YEAR:
            log.warning(kv(event="holiday_table_outdated", year=d.year,
                           note="NYSE_HOLIDAYS tablosunu guncelleyin"))
        return d.weekday() < 5 and d not in NYSE_HOLIDAYS

    def session_times(self, d: date) -> tuple[datetime, datetime] | None:
        """(acilis, kapanis) ET; islem gunu degilse None."""
        if not self.is_trading_day(d):
            return None
        close = _EARLY_CLOSE if d in NYSE_EARLY_CLOSE else _CLOSE
        return (datetime.combine(d, _OPEN, tzinfo=ET),
                datetime.combine(d, close, tzinfo=ET))

    def is_session_open(self, dt: datetime | None = None) -> bool:
        dt = dt or self.now_et()
        times = self.session_times(dt.date())
        return times is not None and times[0] <= dt < times[1]

    def next_trading_day(self, d: date) -> date:
        nxt = d + timedelta(days=1)
        while not self.is_trading_day(nxt):
            nxt += timedelta(days=1)
        return nxt

    def add_trading_days(self, d: date, n: int) -> date:
        cur = d
        step = 1 if n >= 0 else -1
        for _ in range(abs(n)):
            cur += timedelta(days=step)
            while not self.is_trading_day(cur):
                cur += timedelta(days=step)
        return cur

    def trading_days_between(self, start: date, end: date) -> int:
        """Imzali islem gunu mesafesi: start haric, end dahil. end < start -> negatif."""
        if end == start:
            return 0
        sign = 1 if end > start else -1
        lo, hi = (start, end) if end > start else (end, start)
        count = 0
        cur = lo + timedelta(days=1)
        while cur <= hi:
            if self.is_trading_day(cur):
                count += 1
            cur += timedelta(days=1)
        return sign * count
