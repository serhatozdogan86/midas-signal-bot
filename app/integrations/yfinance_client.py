"""
yfinance toplu veri istemcisi (tarihsel omurga - plan bolum 2).
- Gunluk + 1h mumlar, chunk'lanmis toplu indirme (yfinance yuku/rate icin).
- yfinance resmi olmayan bir kutuphanedir; kirilirsa yalnizca bu sinif ve
  MarketDataService degisir (Polygon/Twelve Data'ya gecis noktasi).
- auto_adjust=True: split/temettu duzeltmeli seri (MA'larin split'te kirilmamasi icin).
"""
from __future__ import annotations

import logging
import time

import pandas as pd

from app.logging_setup import kv

log = logging.getLogger("yfinance")


class YFinanceClient:
    def __init__(self, chunk_size: int = 50, chunk_pause_sec: float = 1.0) -> None:
        self._chunk_size = max(1, chunk_size)
        self._pause = chunk_pause_sec

    def download_bulk(self, symbols: list[str], interval: str,
                      period: str) -> dict[str, pd.DataFrame]:
        """
        Sembol -> OHLCV DataFrame. Basarisiz sembol sozlukte yer almaz;
        ust katman eksigi DATA_MISSING olarak ele alir - tahmin yapilmaz.
        """
        import yfinance as yf  # lazy: testler ag/kutuphane olmadan calisir

        out: dict[str, pd.DataFrame] = {}
        symbols = list(dict.fromkeys(s.upper() for s in symbols))
        for i in range(0, len(symbols), self._chunk_size):
            chunk = symbols[i:i + self._chunk_size]
            try:
                data = yf.download(chunk, period=period, interval=interval,
                                   group_by="ticker", auto_adjust=True,
                                   progress=False, threads=True)
            except Exception as exc:
                log.error(kv(event="yf_chunk_error", interval=interval,
                             first=chunk[0], size=len(chunk), error=str(exc)[:200]))
                continue
            if data is None or data.empty:
                log.warning(kv(event="yf_chunk_empty", interval=interval,
                               first=chunk[0], size=len(chunk)))
                continue
            for sym in chunk:
                df = self._extract(data, sym, len(chunk))
                if df is not None and not df.empty:
                    out[sym] = df
            if i + self._chunk_size < len(symbols):
                time.sleep(self._pause)
        log.info(kv(event="yf_bulk_done", interval=interval,
                    requested=len(symbols), received=len(out)))
        return out

    @staticmethod
    def _extract(data: pd.DataFrame, symbol: str, chunk_len: int) -> pd.DataFrame | None:
        try:
            if chunk_len == 1 and not isinstance(data.columns, pd.MultiIndex):
                df = data
            elif isinstance(data.columns, pd.MultiIndex):
                if symbol not in data.columns.get_level_values(0):
                    return None
                df = data[symbol]
            else:
                return None
            return df.dropna(how="all")
        except Exception:
            log.exception(kv(event="yf_extract_error", symbol=symbol))
            return None
