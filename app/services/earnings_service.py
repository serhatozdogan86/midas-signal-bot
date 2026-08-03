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
_RETRY_SEC = 600          # veri yokken 10 dk'da bir tekrar dene


class EarningsService:
    def __init__(self, finnhub: FinnhubClient, calendar: MarketCalendar) -> None:
        self._finnhub = finnhub
        self._calendar = calendar
        self._lock = threading.Lock()
        self._dates: dict[str, list[date]] = {}
        self._fetched_at = 0.0
        # v3.16: takvim yuklendi mi + basarisizlikta HIZLI yeniden deneme.
        # 3 Agu vakasi: prep sirasinda /calendar/earnings timeout'a dustu,
        # _dates BOS kaldi ve bilanco filtresi TUM SEANS BOYUNCA sessizce
        # devre disi kaldi. AMGN'e bilancosuna 1 gun kala LONG sinyali
        # uretildi. TTL 6 saat oldugu icin yeniden deneme de olmadi.
        self._ready = False
        self._last_ok = 0.0
        self._fail_streak = 0

    def refresh(self, today: date, force: bool = False) -> None:
        with self._lock:
            age = time.time() - self._fetched_at
            if not force:
                # veri YOKSA TTL'i bekleme: kisa araliklarla tekrar dene
                limit = _RETRY_SEC if not self._ready else _CACHE_TTL_SEC
                if age < limit:
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
            self._fetched_at = time.time()
            if rows:
                self._dates = mapping
                self._ready = True
                self._last_ok = time.time()
                self._fail_streak = 0
            else:
                self._fail_streak += 1
                log.warning(kv(event="earnings_refresh_failed",
                               fail_streak=self._fail_streak,
                               ready=self._ready))
        log.info(kv(event="earnings_refresh", symbols=len(mapping),
                    window=f"{d_from}..{d_to}"))

    def status(self) -> dict:
        """Teshis: takvim yuklendi mi, kac sembol, ne zaman (v3.16)."""
        with self._lock:
            return {"ready": self._ready, "symbols": len(self._dates),
                    "fail_streak": self._fail_streak,
                    "last_ok_age_min": (round((time.time() - self._last_ok) / 60)
                                        if self._last_ok else None)}

    def info(self, symbol: str, today: date) -> EarningsInfo:
        """Sembole en yakin bilanco tarihi + imzali islem gunu mesafesi."""
        with self._lock:
            dates = list(self._dates.get(symbol.upper(), []))
        if not self._ready:
            # takvim hic yuklenemedi -> "bilmiyoruz" (motor engeller)
            return EarningsInfo(available=False)
        if not dates:
            return EarningsInfo()
        best = min(dates, key=lambda d: abs(self._calendar.trading_days_between(today, d)))
        days = self._calendar.trading_days_between(today, best)
        return EarningsInfo(next_date=best.isoformat(), days_to=days)
