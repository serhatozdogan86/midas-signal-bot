"""
Finnhub ucretsiz API istemcisi.
KRITIK (plan bolum 3): ucretsiz planda stock/candle (OHLCV) endpoint'i KAPALIDIR
(403). Mum verisi ASLA buradan cekilmez. Bu istemci yalnizca:
  - /quote            : gercek zamanli fiyat (Phase 2 ince tarama)
  - /calendar/earnings: bilanco takvimi (Phase 1 EARNINGS filtresi)
Limit: 60 cagri/dk -> izleme listesi boyutunu dogal olarak sinirlar.
"""
from __future__ import annotations

import logging

import requests

from app.logging_setup import kv

log = logging.getLogger("finnhub")

_TIMEOUT = (10, 15)


class FinnhubClient:
    def __init__(self, api_key: str, base_url: str = "https://finnhub.io/api/v1") -> None:
        self._key = api_key
        self._base = base_url.rstrip("/")
        self._session = requests.Session()

    @property
    def configured(self) -> bool:
        return bool(self._key)

    def _get(self, path: str, params: dict) -> dict | None:
        if not self.configured:
            log.warning(kv(event="finnhub_not_configured", path=path))
            return None
        try:
            resp = self._session.get(f"{self._base}{path}",
                                     params={**params, "token": self._key},
                                     timeout=_TIMEOUT)
            if resp.status_code == 429:
                log.warning(kv(event="finnhub_rate_limited", path=path))
                return None
            if resp.status_code != 200:
                log.error(kv(event="finnhub_http_error", path=path,
                             status=resp.status_code))
                return None
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            log.error(kv(event="finnhub_error", path=path, error=str(exc)[:200]))
            return None

    def get_quote(self, symbol: str) -> float | None:
        """Anlik fiyat (Phase 2 ince tarama tetigi)."""
        body = self._get("/quote", {"symbol": symbol.upper()})
        if not body:
            return None
        price = body.get("c")
        return float(price) if price else None

    def get_company_news(self, symbol: str, date_from: str,
                         date_to: str) -> list[dict]:
        """Sirket haberleri (ucretsiz planda ABD hisseleri icin acik).
        [{'datetime': unix, 'headline': .., 'source': .., 'url': .., ...}]"""
        body = self._get("/company-news", {"symbol": symbol.upper(),
                                           "from": date_from, "to": date_to})
        return list(body) if isinstance(body, list) else []

    def get_general_news(self, category: str = "general") -> list[dict]:
        """Genel piyasa haberleri."""
        body = self._get("/news", {"category": category})
        return list(body) if isinstance(body, list) else []

    def get_earnings_calendar(self, date_from: str, date_to: str) -> list[dict]:
        """[{'date': 'YYYY-MM-DD', 'symbol': 'AAPL', ...}, ...]"""
        body = self._get("/calendar/earnings", {"from": date_from, "to": date_to})
        if not body:
            return []
        return list(body.get("earningsCalendar", []))
