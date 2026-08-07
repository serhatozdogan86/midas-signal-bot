"""
NewsService - islem gorulen/izlenen hisselerin haber akisi (dashboard beslemesi).

Kaynak: Finnhub ucretsiz plan - /news (genel piyasa) + /company-news (sembol).
Butce: tur basina 1 genel + en cok NEWS_MAX_SYMBOLS sirket cagrisi (60/dk
limitinin cok altinda). Semboller donel (rotasyon) taranir ki genis izleme
listesi zamanla tam kapsansin. Basliklar dis kaynaktan AYNEN aktarilir ve
dashboard'da boyle etiketlenir; bot haber yorumlamaz (Faz 4+ konusu).

Bellek ici cache: id/url ile tekrarsizlastirilir, zamana gore sirali son
NEWS_KEEP kayit tutulur. Restart'ta sifirlanir (haber gecici veridir,
gist'e yazilmaz).
"""
from __future__ import annotations

import logging
import time
from datetime import date, timedelta

from app.logging_setup import kv

log = logging.getLogger("news")


class NewsService:
    def __init__(self, finnhub, refresh_sec: int = 600,
                 max_symbols: int = 8, keep: int = 60) -> None:
        self._fh = finnhub
        self._interval = refresh_sec
        self._max_symbols = max_symbols
        self._keep = keep
        self._items: list[dict] = []
        self._seen: set = set()
        self._offset = 0
        self._last = 0.0
        self._backoff = 0.0      # devre kesici bekleme (v3.12)
        self._slow_sec = 20.0    # bu suredan uzun tur 'yavas' sayilir
        self.last_refresh_utc: str | None = None

    # ------------------------------------------------------------- refresh
    def maybe_refresh(self, symbols: list[str], today: date) -> None:
        """v3.12: DEVRE KESICI. Finnhub haber ucu yavasladiginda (3 Agu:
        ardisik timeout'lar) her turda tekrar denemek tick'i bosuna
        mesgul eder. Bir tur olcuye gore yavas gecerse bekleme suresi
        katlanir (max 60 dk); hizli ve verimli bir tur normale doner."""
        if time.time() - self._last < self._interval + self._backoff:
            return
        self._last = time.time()
        started = time.time()
        try:
            added = self.refresh(symbols, today)
        except Exception:
            log.exception(kv(event="news_refresh_error"))
            added = None                     # gercek ariza
        elapsed = time.time() - started
        # v4.22: added==0 ARIZA DEGILDIR - sakin bir turda tum basliklar
        # dedup'lidir. Eski kosul her sessiz turda backoff'u katlayip
        # WARNING basiyordu (7 Agu loglari: pespese news_backoff) - "alarm
        # gurultusu alarmi oldurur" dersinin ihlali. Backoff yalniz yavas
        # tur veya exception'da.
        if elapsed > self._slow_sec or added is None:
            prev = self._backoff
            self._backoff = min(max(self._backoff * 2, 300.0), 3600.0)
            if prev != self._backoff:
                log.warning(kv(event="news_backoff", elapsed_s=round(elapsed, 1),
                               added=added, backoff_s=int(self._backoff)))
        elif self._backoff:
            log.info(kv(event="news_backoff_cleared"))
            self._backoff = 0.0

    def refresh(self, symbols: list[str], today: date) -> int:
        added = 0
        for item in self._fh.get_general_news():
            added += self._add(item, symbol=None)

        picked: list[str] = []
        if symbols:
            uniq = list(dict.fromkeys(symbols))
            # rotasyon: her turda farkli dilim -> genis liste zamanla kapsanir
            start = self._offset % len(uniq)
            picked = (uniq[start:] + uniq[:start])[: self._max_symbols]
            self._offset += self._max_symbols
            date_from = (today - timedelta(days=3)).isoformat()
            for symbol in picked:
                for item in self._fh.get_company_news(
                        symbol, date_from, today.isoformat()):
                    added += self._add(item, symbol=symbol)

        self._items.sort(key=lambda x: x["datetime"], reverse=True)
        del self._items[self._keep:]
        self.last_refresh_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                              time.gmtime())
        log.info(kv(event="news_refresh", added=added,
                    total=len(self._items), symbols=len(picked)))
        return added

    def _add(self, raw: dict, symbol: str | None) -> int:
        key = raw.get("id") or raw.get("url")
        headline = (raw.get("headline") or "").strip()
        if not key or key in self._seen or not headline:
            return 0
        self._seen.add(key)
        if len(self._seen) > self._keep * 20:
            self._seen = {i.get("id") or i.get("url") for i in self._items}
        self._items.append({
            "datetime": int(raw.get("datetime") or 0),
            "symbol": symbol or (raw.get("related") or "").split(",")[0] or None,
            "headline": headline[:200],
            "source": (raw.get("source") or "")[:40],
            "url": raw.get("url") or "",
        })
        return 1

    # --------------------------------------------------------------- query
    def items(self, limit: int = 40) -> list[dict]:
        return self._items[:limit]

    def info(self) -> dict:
        return {"count": len(self._items),
                "last_refresh_utc": self.last_refresh_utc}
