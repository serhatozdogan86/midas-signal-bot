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


class KlineSeries(BaseModel):
    """Kronolojik (eski -> yeni) mum serisi."""

    symbol: str
    interval: str
    candles: list[Candle]

    def __len__(self) -> int:
        return len(self.candles)

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
