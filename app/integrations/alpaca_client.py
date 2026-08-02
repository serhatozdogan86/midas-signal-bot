"""
Alpaca Market Data API istemcisi (Asama 0 - PARALEL GOZLEM).

ONEMLI: Bu istemci su an motorun KARARLARINI ETKILEMEZ. Yalnizca yfinance
ile ayni veriyi cekip karsilastirmak icin kullanilir (bkz.
services/data_comparison.py). Amac, ana veri kaynagini degistirmeden once
"Alpaca gercekten daha mi guvenilir?" sorusunu VERIYLE cevaplamak.

Ucretsiz (Basic) plan kisitlari - 2 Agu 2026 itibariyla:
  - Gecmis veri 2016'dan itibaren, ancak SON 15 DAKIKA sorgulanamaz
  - Gercek zamanli veri yalnizca IEX borsasindan (~%2.5 hacim payi)
  - 200 istek/dk
Bu yuzden karsilastirmada son (olusmakta olan) bar disarida birakilir.

Cikti sozlesmesi YFinanceClient ile AYNIDIR: sembol -> OHLCV DataFrame
(kolonlar: Open/High/Low/Close/Volume, indeks: zaman damgasi) - boylece
ayni KlineSeries.from_dataframe donusumu kullanilabilir.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

from app.logging_setup import kv

log = logging.getLogger("alpaca")

_BASE = "https://data.alpaca.markets/v2"
_TIMEFRAME = {"1d": "1Day", "1h": "1Hour"}
_MAX_SYMBOLS_PER_REQ = 100      # coklu-sembol bar sorgusu (istek tasarrufu)
_FREE_PLAN_DELAY_MIN = 16       # 15 dk kisit + 1 dk emniyet payi


class AlpacaClient:
    """Alpaca gecmis bar verisi. Anahtar yoksa sessizce devre disidir."""

    def __init__(self, api_key: str = "", api_secret: str = "",
                 feed: str = "iex", timeout: float = 20.0) -> None:
        self._key = api_key
        self._secret = api_secret
        self._feed = feed
        self._timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self._key and self._secret)

    def _headers(self) -> dict:
        return {"APCA-API-KEY-ID": self._key,
                "APCA-API-SECRET-KEY": self._secret}

    def download_bulk(self, symbols: list[str], interval: str,
                      lookback_days: int = 90) -> dict[str, pd.DataFrame]:
        """Sembol -> OHLCV DataFrame. Basarisiz sembol sozlukte YER ALMAZ
        (yfinance istemcisiyle ayni davranis: tahmin yok, eksik eksiktir)."""
        if not self.enabled:
            return {}
        tf = _TIMEFRAME.get(interval)
        if tf is None:
            log.warning(kv(event="alpaca_bad_interval", interval=interval))
            return {}

        symbols = list(dict.fromkeys(s.upper() for s in symbols))
        end = datetime.now(timezone.utc) - timedelta(minutes=_FREE_PLAN_DELAY_MIN)
        start = end - timedelta(days=lookback_days)
        out: dict[str, pd.DataFrame] = {}

        for i in range(0, len(symbols), _MAX_SYMBOLS_PER_REQ):
            chunk = symbols[i:i + _MAX_SYMBOLS_PER_REQ]
            try:
                frames = self._fetch_chunk(chunk, tf, start, end)
            except Exception:
                log.exception(kv(event="alpaca_chunk_error", n=len(chunk)))
                continue
            out.update(frames)

        log.info(kv(event="alpaca_bulk_done", interval=interval,
                    requested=len(symbols), received=len(out)))
        return out

    def _fetch_chunk(self, chunk: list[str], tf: str,
                     start: datetime, end: datetime) -> dict[str, pd.DataFrame]:
        raw: dict[str, list] = {}
        page_token = None
        for _ in range(10):                       # sayfalama emniyet siniri
            params = {
                "symbols": ",".join(chunk),
                "timeframe": tf,
                "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "limit": 10000,
                "adjustment": "split",            # yfinance varsayilanina yakin
                "feed": self._feed,
            }
            if page_token:
                params["page_token"] = page_token
            r = requests.get(f"{_BASE}/stocks/bars", params=params,
                             headers=self._headers(), timeout=self._timeout)
            if r.status_code != 200:
                log.warning(kv(event="alpaca_http_error", status=r.status_code,
                               body=r.text[:200]))
                break
            body = r.json() or {}
            for sym, bars in (body.get("bars") or {}).items():
                raw.setdefault(sym, []).extend(bars)
            page_token = body.get("next_page_token")
            if not page_token:
                break

        out: dict[str, pd.DataFrame] = {}
        for sym, bars in raw.items():
            df = self._to_frame(bars)
            if df is not None and not df.empty:
                out[sym] = df
        return out

    @staticmethod
    def _to_frame(bars: list) -> pd.DataFrame | None:
        """Alpaca bar sozlugunu YFinanceClient ciktisiyla ayni sekle cevirir."""
        if not bars:
            return None
        try:
            df = pd.DataFrame(bars)
            df["t"] = pd.to_datetime(df["t"], utc=True)
            df = df.set_index("t").sort_index()
            df = df.rename(columns={"o": "Open", "h": "High", "l": "Low",
                                     "c": "Close", "v": "Volume"})
            return df[["Open", "High", "Low", "Close", "Volume"]]
        except Exception:
            log.exception(kv(event="alpaca_frame_error"))
            return None
