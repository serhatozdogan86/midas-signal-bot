"""
EarningsService - Finnhub bilanco takvimi + cache (plan bolum 6 yeni modul).
EARNINGS hard filtresinin veri kaynagi: bilancoya +-N islem gunu -> sinyal yok.
Kapsam boslugu olabilir (ucretsiz plan); tarih bilinmiyorsa engine filtreyi
GECIRIR ancak earnings_date alani bos kalir (mesajda 'bilinmiyor' gorunur).
"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
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
# v4.22: "veri var" != "veri guncel" (v3.17 ilkesinin takvime uygulanmasi).
# Takvim bir kez yuklendikten sonra Finnhub uzun sure cokerse eski _dates
# sessizce guncel gibi kullaniliyordu ve denetim ready=True gorup YESIL
# kaliyordu. Son basarili yuklemeden bu kadar sure gectiyse takvim BAYAT
# sayilir -> fail-closed (2.2) devreye girer, sinyal uretilmez.
_STALE_SEC = 24 * 3600


class EarningsService:
    def __init__(self, finnhub: FinnhubClient, calendar: MarketCalendar,
                 fallback=None) -> None:
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
        # v3.18 YEDEK KAYNAK (yfinance). Finnhub takvimi coktugunde
        # YALNIZ pass-2 adaylari icin (~50 sembol) sembol basina
        # sorgulanir; pass-1 (300 sembol) asla yedege gitmez.
        self._fallback = fallback          # callable(symbol) -> [date] | [] | None
        self._fb_dates: dict[str, list] = {}   # basarili sonuclar
        self._fb_failed: set[str] = set()      # hata alanlar (bilmiyoruz)
        self._fb_day: date | None = None

    def _fresh_ready(self) -> bool:
        """Takvim yuklu VE bayat degil (kilit altinda cagrilmali)."""
        return self._ready and (time.time() - self._last_ok) < _STALE_SEC

    def refresh(self, today: date, force: bool = False) -> None:
        with self._lock:
            age = time.time() - self._fetched_at
            if not force:
                # veri YOKSA/BAYATSA/son deneme BASARISIZSA TTL'i bekleme:
                # kisa araliklarla tekrar dene (v4.22: eskiden ready=True
                # iken basarisiz yenileme 6 saatlik TTL'e mahkum kaliyordu).
                limit = (_CACHE_TTL_SEC
                         if self._fresh_ready() and self._fail_streak == 0
                         else _RETRY_SEC)
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

    def prefetch(self, symbols: list[str], today: date) -> None:
        """Finnhub takvimi yoksa aday semboller icin yedek kaynagi calistir.
        Gunde bir kez sembol basina; hata alanlar tekrar denenmez (o gun)."""
        with self._lock:
            fresh = self._fresh_ready()
        if fresh or self._fallback is None or not symbols:
            return
        with self._lock:
            if self._fb_day != today:            # gun donunce onbellek sifirlanir
                self._fb_dates, self._fb_failed, self._fb_day = {}, set(), today
            need = [s for s in symbols
                    if s not in self._fb_dates and s not in self._fb_failed]
        if not need:
            return
        ok = 0
        with ThreadPoolExecutor(max_workers=4) as pool:
            for sym, res in zip(need, pool.map(self._fallback, need)):
                with self._lock:
                    if res is None:
                        self._fb_failed.add(sym)
                    else:
                        self._fb_dates[sym] = list(res)
                        ok += 1
        log.warning(kv(event="earnings_fallback_used", requested=len(need),
                       ok=ok, failed=len(need) - ok))

    def status(self) -> dict:
        """Teshis: takvim yuklendi mi, kac sembol, ne zaman (v3.16).
        v4.22: ready artik TAZELIK icerir - bayat takvim ready=False."""
        with self._lock:
            return {"ready": self._fresh_ready(), "symbols": len(self._dates),
                    "fallback_ok": len(self._fb_dates),
                    "fallback_failed": len(self._fb_failed),
                    "fail_streak": self._fail_streak,
                    "last_ok_age_min": (round((time.time() - self._last_ok) / 60)
                                        if self._last_ok else None)}

    def info(self, symbol: str, today: date,
             strict: bool = True) -> EarningsInfo:
        """Sembole en yakin bilanco tarihi + imzali islem gunu mesafesi.

        strict=False YALNIZCA pass-1 icindir: o gecis SIGNAL uretemez
        (1h verisi yok), sadece aday eler. Takvim yokken pass-1'i
        kilitlersek hicbir aday pass-2'ye ulasmaz ve yedek kaynak da
        hic calismaz - kilitlenme olurdu.
        """
        sym = symbol.upper()
        with self._lock:
            dates = list(self._dates.get(sym, []))
            fb = self._fb_dates.get(sym)
            fb_failed = sym in self._fb_failed
            fresh = self._fresh_ready()
        if not fresh:
            if fb is not None:                 # yedek kaynaktan geldi
                dates = list(fb)
                if not dates:
                    return EarningsInfo()
            elif fb_failed or strict:
                return EarningsInfo(available=False)
            else:
                return EarningsInfo()          # pass-1: eleme yapma
        if not dates:
            return EarningsInfo()
        best = min(dates, key=lambda d: abs(self._calendar.trading_days_between(today, d)))
        days = self._calendar.trading_days_between(today, best)
        return EarningsInfo(next_date=best.isoformat(), days_to=days)
