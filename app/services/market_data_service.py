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
                 daily_period: str = "2y", hourly_period: str = "60d",
                 alpaca=None) -> None:
        self._yf = yf_client
        self._finnhub = finnhub
        self._alpaca = alpaca
        self._alpaca_fb_logged = False
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
        """Gercek zamanli fiyat (Phase 2 - ince tarama tetigi).
        v3.20: Finnhub -> Alpaca yedegi. 3-4 Agu Finnhub kesintisinde
        kill-switch/ince tarama/gap nobeti KOR kalmisti; artik ikinci
        kaynak var. Ikisi de yoksa None (fail-open zincirleri ayni)."""
        q = self._finnhub.get_quote(symbol) if self._finnhub else None
        if q is not None:
            return q
        snap = self._alpaca_snap(symbol)
        return snap["price"] if snap else None

    def get_quote_change(self, symbol: str) -> dict | None:
        q = self._finnhub.get_quote_change(symbol) if self._finnhub else None
        if q is not None:
            return q
        snap = self._alpaca_snap(symbol)
        if not snap or snap.get("prev_close") is None:
            return None
        price, prev = snap["price"], snap["prev_close"]
        return {"price": price,
                "pct": round((price / prev - 1) * 100, 2)}

    def _alpaca_snap(self, symbol: str) -> dict | None:
        if self._alpaca is None or not getattr(self._alpaca, "enabled", False):
            return None
        if not self._alpaca_fb_logged:
            # gorunurluk: yedegin devrede oldugu nabizda bir kez gorunsun
            log.warning(kv(event="quote_fallback_alpaca_active"))
            self._alpaca_fb_logged = True
        sym = symbol.upper()          # sozlesme: istemciye BUYUK harf gider
        return (self._alpaca.get_snapshots([sym]) or {}).get(sym)

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
