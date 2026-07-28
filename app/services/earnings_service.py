"""
EarningsService - Finnhub bilanco takvimi + cache (plan bolum 6 yeni modul).
EARNINGS hard filtresinin veri kaynagi: bilancoya +-N islem gunu -> sinyal yok.
Kapsam boslugu olabilir (ucretsiz plan); tarih bilinmiyorsa engine filtreyi
GECIRIR ancak earnings_date alani bos kalir (mesajda 'bilinmiyor' gorunur).
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import date, timedelta

from app.integrations.finnhub_client import FinnhubClient
from app.logging_setup import kv
from app.models.decision import EarningsInfo
from app.services.market_calendar import MarketCalendar

log = logging.getLogger("earnings")

_WINDOW_BACK_DAYS = 4     # yeni acilanan bilanco da blackout'a girer
_WINDOW_FWD_DAYS = 14
_CACHE_TTL_SEC = 6 * 3600


class EarningsService:
    def __init__(self, finnhub: FinnhubClient, calendar: MarketCalendar) -> None:
        self._finnhub = finnhub
        self._calendar = calendar
        self._lock = threading.Lock()
        self._dates: dict[str, list[date]] = {}
        self._fetched_at = 0.0

    def refresh(self, today: date, force: bool = False) -> None:
        with self._lock:
            if not force and (time.time() - self._fetched_at) < _CACHE_TTL_SEC:
                return
        d_from = (today - timedelta(days=_WINDOW_BACK_DAYS)).isoformat()
        d_to = (today + timedelta(days=_WINDOW_FWD_DAYS)).isoformat()
        rows = self._finnhub.get_earnings_calendar(d_from, d_to)
        mapping: dict[str, list[date]] = {}
        for row in rows:
            sym = str(row.get("symbol", "")).upper()
            raw = str(row.get("date", ""))
            if not sym or not raw:
                continue
            try:
                mapping.setdefault(sym, []).append(date.fromisoformat(raw))
            except ValueError:
                continue
        with self._lock:
            if rows:
                self._dates = mapping
                self._fetched_at = time.time()
        log.info(kv(event="earnings_refresh", symbols=len(mapping),
                    window=f"{d_from}..{d_to}"))

    def info(self, symbol: str, today: date) -> EarningsInfo:
        """Sembole en yakin bilanco tarihi + imzali islem gunu mesafesi."""
        with self._lock:
            dates = list(self._dates.get(symbol.upper(), []))
        if not dates:
            return EarningsInfo()
        best = min(dates, key=lambda d: abs(self._calendar.trading_days_between(today, d)))
        days = self._calendar.trading_days_between(today, best)
        return EarningsInfo(next_date=best.isoformat(), days_to=days)
