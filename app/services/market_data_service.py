"""
Market data erisim katmani - iki kaynakli soyutlama (plan bolum 2/6):
  - Tarihsel omurga : yfinance (1d + 1h, toplu)
  - Gercek zamanli  : Finnhub quote (Phase 2 ince tarama; metod hazir)
Engine bu servis uzerinden veri alir. Kaynak degisirse (Polygon/Twelve Data)
yalnizca bu sinif + ilgili istemci degisir.
"""
from __future__ import annotations

import logging

from app.integrations.finnhub_client import FinnhubClient
from app.integrations.yfinance_client import YFinanceClient
from app.logging_setup import kv
from app.models.candle import KlineSeries

log = logging.getLogger("market_data")


class MarketDataService:
    def __init__(self, yf_client: YFinanceClient,
                 finnhub: FinnhubClient | None = None,
                 daily_period: str = "2y", hourly_period: str = "60d") -> None:
        self._yf = yf_client
        self._finnhub = finnhub
        self._daily_period = daily_period
        self._hourly_period = hourly_period

    def get_daily_bulk(self, symbols: list[str],
                       period: str | None = None) -> dict[str, KlineSeries]:
        """period=None -> tam omurga (2y). Hafif kullanimlar (likidite filtresi)
        icin kisa period gecilebilir (or. '1mo') - istek yuku ayni ama yuk hafif."""
        return self._to_series(
            self._yf.download_bulk(symbols, "1d", period or self._daily_period), "1d")

    def get_hourly_bulk(self, symbols: list[str]) -> dict[str, KlineSeries]:
        return self._to_series(self._yf.download_bulk(symbols, "1h", self._hourly_period), "1h")

    def get_quote(self, symbol: str) -> float | None:
        """Gercek zamanli fiyat (Phase 2 - ince tarama tetigi)."""
        if self._finnhub is None:
            return None
        return self._finnhub.get_quote(symbol)

    def get_quote_change(self, symbol: str) -> dict | None:
        if self._finnhub is None:
            return None
        return self._finnhub.get_quote_change(symbol)

    @staticmethod
    def _to_series(frames: dict, interval: str) -> dict[str, KlineSeries]:
        out: dict[str, KlineSeries] = {}
        for sym, df in frames.items():
            try:
                series = KlineSeries.from_dataframe(sym, interval, df)
            except ValueError:
                log.warning(kv(event="series_convert_error", symbol=sym,
                               interval=interval))
                continue
            if len(series):
                out[sym] = series
        return out
