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
import time

import requests

from app.logging_setup import kv

log = logging.getLogger("finnhub")

_NEWS_TIMEOUT = 5.0   # haber uclari icin kisa (kozmetik veri)
_TIMEOUT = (10, 15)


class FinnhubClient:
    def __init__(self, api_key: str, base_url: str = "https://finnhub.io/api/v1") -> None:
        self._key = api_key
        self._base = base_url.rstrip("/")
        self._session = requests.Session()
        self._fail_count = 0        # ardisik 5xx (v4.7)
        self._blocked_until = 0.0   # devre kesici bitisi

    @property
    def configured(self) -> bool:
        return bool(self._key)

    def _trip(self, path: str) -> None:
        self._fail_count += 1
        if self._fail_count >= 5:
            self._blocked_until = time.time() + min(
                60.0 * (2 ** (self._fail_count - 5)), 600.0)

    def _reset_breaker(self) -> None:
        if self._fail_count:
            log.info(kv(event="finnhub_recovered", fails=self._fail_count))
        self._fail_count = 0
        self._blocked_until = 0.0

    def breaker_open(self) -> bool:
        return time.time() < self._blocked_until

    def _get(self, path: str, params: dict,
             timeout: float | None = None) -> dict | None:
        if not self.configured:
            log.warning(kv(event="finnhub_not_configured", path=path))
            return None
        if self.breaker_open():
            # saglayici cokuk: bosuna deneme, cagiran yedege gecsin
            return None
        try:
            resp = self._session.get(f"{self._base}{path}",
                                     params={**params, "token": self._key},
                                     timeout=timeout or _TIMEOUT)
            if resp.status_code == 429:
                log.warning(kv(event="finnhub_rate_limited", path=path))
                return None
            if resp.status_code != 200:
                # v4.7: SAGLAYICI ARIZASI (5xx) bizim hatamiz degil ve
                # YEDEGIMIZ var (Alpaca). 4 Agu gecesi tek kesintide 30
                # ERROR satiri dustu; gercek bir sorun bu gurultunun
                # icinde kaybolur. 5xx -> WARNING + devre kesici;
                # 4xx (yanlis anahtar/istek) -> ERROR olarak KALIR.
                if 500 <= resp.status_code < 600:
                    self._trip(path)
                    log.warning(kv(event="finnhub_provider_down", path=path,
                                   status=resp.status_code,
                                   fails=self._fail_count))
                else:
                    log.error(kv(event="finnhub_http_error", path=path,
                                 status=resp.status_code))
                return None
            self._reset_breaker()
            return resp.json()
        except requests.RequestException as exc:
            # v4.22 (acik kuyruk #4): timeout/baglanti kesintisi de saglayici
            # arizasidir - 5xx gibi devre kesiciyi acar (3 Agu kesintisinin
            # asil modu timeout'tu; breaker acilmayinca her cagri 10+15 sn
            # bekleyip taramayi kilitliyordu) ve WARNING'e iner (yedek var).
            self._trip(path)
            log.warning(kv(event="finnhub_provider_down", path=path,
                           error=str(exc)[:200], fails=self._fail_count))
            return None
        except ValueError as exc:
            log.error(kv(event="finnhub_error", path=path, error=str(exc)[:200]))
            return None

    def get_quote(self, symbol: str) -> float | None:
        """Anlik fiyat (Phase 2 ince tarama tetigi)."""
        body = self._get("/quote", {"symbol": symbol.upper()})
        if not body:
            return None
        price = body.get("c")
        return float(price) if price else None

    def get_company_profile(self, symbol: str) -> dict | None:
        """Sirket kimligi (/stock/profile2 - ucretsiz planda ACIK).
        Doner: {'finnhubIndustry','marketCapitalization' (mn $),'name',...}"""
        body = self._get("/stock/profile2", {"symbol": symbol.upper()})
        return body if isinstance(body, dict) and body else None

    def get_basic_financials(self, symbol: str) -> dict | None:
        """Temel oranlar (/stock/metric?metric=all). Ucretsiz planda
        kisitli olabilir -> None donerse cagiran KISMI veriyle devam eder."""
        body = self._get("/stock/metric", {"symbol": symbol.upper(),
                                           "metric": "all"})
        if not isinstance(body, dict):
            return None
        metric = body.get("metric")
        return metric if isinstance(metric, dict) and metric else None

    def get_quote_change(self, symbol: str) -> dict | None:
        """Anlik fiyat + onceki kapanisa gore % degisim (header endeks cipi)."""
        body = self._get("/quote", {"symbol": symbol.upper()})
        if not body or not body.get("c") or not body.get("pc"):
            return None
        c, pc = float(body["c"]), float(body["pc"])
        return {"price": c, "pct": round((c / pc - 1) * 100, 2)}

    def get_company_news(self, symbol: str, date_from: str,
                         date_to: str) -> list[dict]:
        """Sirket haberleri (ucretsiz planda ABD hisseleri icin acik).
        [{'datetime': unix, 'headline': .., 'source': .., 'url': .., ...}]"""
        # v3.12: haber KOZMETIKTIR, islem kararlarina girmez -> kisa
        # timeout. Uzun timeout tick dongusunu kilitliyordu (3 Agu:
        # 5 sembol x 15 sn = 75 sn blokaj, gap nobetinin onunde).
        body = self._get("/company-news", {"symbol": symbol.upper(),
                                           "from": date_from, "to": date_to},
                         timeout=_NEWS_TIMEOUT)
        return list(body) if isinstance(body, list) else []

    def get_general_news(self, category: str = "general") -> list[dict]:
        """Genel piyasa haberleri."""
        body = self._get("/news", {"category": category},
                         timeout=_NEWS_TIMEOUT)
        return list(body) if isinstance(body, list) else []

    def get_earnings_calendar(self, date_from: str, date_to: str) -> list[dict]:
        """[{'date': 'YYYY-MM-DD', 'symbol': 'AAPL', ...}, ...]"""
        body = self._get("/calendar/earnings", {"from": date_from, "to": date_to})
        if not body:
            return []
        return list(body.get("earningsCalendar", []))
