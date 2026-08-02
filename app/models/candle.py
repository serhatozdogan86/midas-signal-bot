"""Piyasa verisi modelleri."""
from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, Field


class Candle(BaseModel):
    """Tek OHLCV mumu."""

    ts: int = Field(description="Acilis zamani (ms epoch)")
    open: float
    high: float
    low: float
    close: float
    volume: float


_INTERVAL_MS = {"1h": 3_600_000, "1d": 86_400_000}


class KlineSeries(BaseModel):
    """Kronolojik (eski -> yeni) mum serisi."""

    symbol: str
    interval: str
    candles: list[Candle]

    def __len__(self) -> int:
        return len(self.candles)

    def closed_only(self, now_ms: int | None = None) -> "KlineSeries":
        """Olusmakta olan (henuz kapanmamis) son bari atar.

        2 Agu bulgusu: motor SETUP tetigini (donus mumu / kirilim mumu)
        serinin SON bari uzerinde ariyordu. Kaba tarama 15 dk'da bir
        kostugu icin o bar dort seferin ucunde HENUZ KAPANMAMISTI - yani
        sinyalin dayandigi mum, saat kapaninca bambaska gorunebiliyordu
        ("repaint"). Gelecek veri kullanilmiyor (look-ahead degil) ama
        gerekcesi buharlasmis sinyal uretilebiliyordu."""
        import time as _t

        if not self.candles:
            return self
        now_ms = now_ms if now_ms is not None else int(_t.time() * 1000)
        step = _INTERVAL_MS.get(self.interval)
        if step is None:
            return self
        last = self.candles[-1]
        if last.ts + step > now_ms:                 # bar penceresi kapanmadi
            return KlineSeries(symbol=self.symbol, interval=self.interval,
                               candles=self.candles[:-1])
        return self

    def to_dataframe(self) -> pd.DataFrame:
        """Engine'in kullandigi DataFrame temsili (kolonlar sabit)."""
        return pd.DataFrame([c.model_dump() for c in self.candles])

    @classmethod
    def from_dataframe(cls, symbol: str, interval: str, df: pd.DataFrame) -> "KlineSeries":
        """
        yfinance DataFrame'ini modele cevirir.
        Beklenen kolonlar (case-insensitive): Open/High/Low/Close/Volume; index = zaman.
        NaN satirlar (tatil/eksik bar) atilir.
        """
        cols = {str(c).lower(): c for c in df.columns}
        need = ["open", "high", "low", "close", "volume"]
        if any(k not in cols for k in need):
            raise ValueError(f"unexpected columns: {list(df.columns)}")
        sub = df[[cols[k] for k in need]].copy()
        sub.columns = need
        sub = sub.dropna(subset=["open", "high", "low", "close"])
        candles = []
        for idx, row in sub.iterrows():
            ts = int(pd.Timestamp(idx).value // 1_000_000)  # ns -> ms
            candles.append(Candle(
                ts=ts, open=float(row["open"]), high=float(row["high"]),
                low=float(row["low"]), close=float(row["close"]),
                volume=float(row["volume"]) if pd.notna(row["volume"]) else 0.0,
            ))
        return cls(symbol=symbol, interval=interval, candles=candles)
