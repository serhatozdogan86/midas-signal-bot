"""
Pipeline adim 8: risk / hedef hesabi. Saf fonksiyon.

Plan bolum 2 kilitli kararlari:
  TP1 = entry + 1 x gunluk ATR, TP2 = entry + 2 x gunluk ATR (short'ta ayna)
  Stop = ATR bazli: yapisal stop (son 1h swing ucu + tampon), ust siniri
         entry -/+ ATR_STOP_MULT x gunluk ATR.
  RR   = (TP2 - entry) / risk  >= min esik   (tasarim notu: README "RR tanimi")
  Maliyet filtresi: TP1 mesafesi (%) >= MIN_TARGET_PCT (Midas 1.5$/islem geregi)
Esikler signal_engine'de uygulanir; burada yalnizca hesap yapilir.
"""
from __future__ import annotations

import math

import pandas as pd
from pydantic import BaseModel

from app.config.settings import StrategyParams
from app.models.decision import Direction
from app.strategies.indicators import atr
from app.strategies.structure_analyzer import SetupCandidate

_STRUCT_BUFFER_ATR = 0.1  # yapisal stopa eklenen tampon (gunluk ATR carpani)


class TradePlan(BaseModel):
    entry_min: float
    entry_max: float
    stop_loss: float
    tp1: float
    tp2: float
    rr: float
    target_pct: float       # TP1 mesafesi (%) - maliyet filtresi girdisi
    atr_daily: float


def build_trade_plan(hourly: pd.DataFrame, daily: pd.DataFrame,
                     direction: Direction, setup: SetupCandidate,
                     params: StrategyParams) -> TradePlan | None:
    """Plan kurulamazsa (risk <= 0) None -> NO_TRADE."""
    atr_d = float(atr(daily).iloc[-1])
    if atr_d <= 0:
        return None
    close = float(hourly["close"].iloc[-1])
    level = setup.level
    lows = hourly["low"].values
    highs = hourly["high"].values
    look = params.stop_lookback_bars

    entry_min, entry_max = sorted((level, close))
    entry_mid = (entry_min + entry_max) / 2

    if direction is Direction.LONG:
        stop_struct = float(min(lows[-look:])) - _STRUCT_BUFFER_ATR * atr_d
        stop_cap = entry_mid - params.atr_stop_mult * atr_d
        stop = max(stop_struct, stop_cap)      # yapisal stop, ATR ust siniriyla
        risk = entry_mid - stop
        tp1 = entry_mid + params.atr_tp1_mult * atr_d
        tp2 = entry_mid + params.atr_tp2_mult * atr_d
        reward = tp2 - entry_mid
        target_pct = (tp1 - entry_mid) / entry_mid * 100
    else:
        stop_struct = float(max(highs[-look:])) + _STRUCT_BUFFER_ATR * atr_d
        stop_cap = entry_mid + params.atr_stop_mult * atr_d
        stop = min(stop_struct, stop_cap)
        risk = stop - entry_mid
        tp1 = entry_mid - params.atr_tp1_mult * atr_d
        tp2 = entry_mid - params.atr_tp2_mult * atr_d
        reward = entry_mid - tp2
        target_pct = (entry_mid - tp1) / entry_mid * 100

    if risk <= 0 or entry_mid <= 0:
        return None
    # v3.9.4 SAVUNMA DERINLIGI (dis inceleme bulgusu): NaN karsilastirmalari
    # HER ZAMAN False doner -> yukaridaki 'risk <= 0' ve motordaki RR/maliyet
    # filtreleri NaN'i sessizce GECIRIR ve NaN hedefli bir SIGNAL uretilebilir.
    # Bugun sizmiyor (KlineSeries.from_dataframe NaN barlari dusuruyor) ama
    # koruma tek katmanda olmamali: veri yolu degisirse sessiz felaket olur.
    vals = (entry_min, entry_max, stop, tp1, tp2, risk, reward, target_pct, atr_d)
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in vals):
        return None
    return TradePlan(
        entry_min=round(entry_min, 4),
        entry_max=round(entry_max, 4),
        stop_loss=round(stop, 4),
        tp1=round(tp1, 4),
        tp2=round(tp2, 4),
        rr=round(reward / risk, 2),
        target_pct=round(target_pct, 2),
        atr_daily=round(atr_d, 4),
    )
