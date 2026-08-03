"""v3.17 - 'sessizce gecer mi?' denetimi.

3 Agu bilanco vakasindan sonra TUM karar filtreleri ayni gozle tarandi:
verisi gelmezse filtre sessizce 'gecer' mi diyor? Bu dosya bulgulari
ve duzeltmeleri kilitler.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from app.config.settings import Settings
from app.models.decision import (Bias, DecisionType, EarningsInfo,
                                 MarketRegime)
from app.services.market_calendar import NYSE_HOLIDAYS, _TABLE_MAX_YEAR
from app.strategies import signal_engine
from app.strategies.regime_detector import RegimeResult
from app.strategies.volume_analyzer import validate_event_volume
from tests import fixtures as fx

P = Settings().strategy_params
E_FAR = EarningsInfo(next_date="2026-12-20", days_to=90)


def _inputs():
    daily = fx.make_series(fx.daily_uptrend_closes(), interval="1d",
                           spread=0.02)
    hourly = fx.make_series(fx.hourly_pullback_long_closes(),
                            volumes=fx.spike_volumes(110))
    bench = fx.make_series(fx.daily_uptrend_closes(), interval="1d",
                           spread=0.02).to_dataframe()
    return daily, hourly, bench


def test_baseline_produces_signal():
    """Denetim testlerinin anlamli olmasi icin temel senaryo SIGNAL
    vermeli; aksi halde 'engelledi' iddialari bosa duser."""
    daily, hourly, bench = _inputs()
    d = signal_engine.evaluate("AAPL", daily, hourly,
                               RegimeResult(regime=MarketRegime.BULL),
                               P, bench, E_FAR)
    assert d.decision is DecisionType.SIGNAL


def test_stale_daily_data_is_rejected():
    """v3.17: 'veri var' ile 'veri guncel' ayni sey degil. yfinance
    bozuk yanitta haftalik eski mumlar dondurebilir."""
    daily, hourly, bench = _inputs()
    old = daily.model_copy(deep=True)
    shift = 20 * 86_400_000
    for c in old.candles:
        c.ts -= shift
    d = signal_engine.evaluate("AAPL", old, hourly,
                               RegimeResult(regime=MarketRegime.BULL),
                               P, bench, E_FAR)
    assert d.decision is DecisionType.DATA_MISSING
    assert "daily_stale" in (d.data_missing or [])


def test_unknown_regime_blocks():
    daily, hourly, bench = _inputs()
    d = signal_engine.evaluate("AAPL", daily, hourly,
                               RegimeResult(regime=MarketRegime.UNKNOWN,
                                            detail="veri yok"),
                               P, bench, E_FAR)
    assert d.decision is not DecisionType.SIGNAL
    assert "MARKET_REGIME" in (d.failed_filters or [])


def test_missing_volume_data_blocks():
    """Hacim ortalamasi hesaplanamiyorsa teyit YOK sayilir (gecmez)."""
    import pandas as pd
    df = pd.DataFrame({"volume": [0.0] * 40, "close": [1.0] * 40})
    ok, ratio = validate_event_volume(df, -1, 1.5)
    assert ok is False and ratio == 0.0


def test_missing_benchmark_blocks_short_not_long():
    """SHORT zayif RS sarti benchmark yoksa saglanmaz (fail-closed);
    LONG benchmark'siz calisabilir (RS yalnizca confluence)."""
    daily = fx.make_series(fx.daily_downtrend_closes(), interval="1d",
                           spread=0.02)
    hourly = fx.make_series(fx.hourly_pullback_short_closes(),
                            volumes=fx.spike_volumes(110))
    d = signal_engine.evaluate("XYZ", daily, hourly,
                               RegimeResult(regime=MarketRegime.BEAR),
                               P, None, E_FAR)
    assert d.decision is not DecisionType.SIGNAL

    daily2, hourly2, _ = _inputs()
    d2 = signal_engine.evaluate("AAPL", daily2, hourly2,
                                RegimeResult(regime=MarketRegime.BULL),
                                P, None, E_FAR)
    assert d2.decision is DecisionType.SIGNAL


def test_gap_watch_alerts_when_position_quote_missing():
    """Koruyucu kontrol atlanirsa SESSIZ KALINMAZ."""
    from pathlib import Path
    src = Path("app/scheduler.py").read_text()
    assert "gap_watch_quote_missing" in src
    assert "KONTROL EDILEMEDI" in src
    assert '"positions_unchecked": missing_pos,' in src


def test_holiday_table_not_near_expiry():
    """ONLEYICI: statik NYSE tatil tablosu bitmeden 120 gun once bu test
    KIRILIR ve tabloyu guncellememizi zorlar. Tablo bitince kod tatilleri
    normal islem gunu sanar (sessiz fail-open)."""
    table_end = date(_TABLE_MAX_YEAR, 12, 31)
    remaining = (table_end - date.today()).days
    assert remaining > 120, (
        f"NYSE tatil tablosu {remaining} gun sonra bitiyor - "
        "market_calendar.py icindeki NYSE_HOLIDAYS'i uzatin")
    assert NYSE_HOLIDAYS, "tatil tablosu bos olamaz"
