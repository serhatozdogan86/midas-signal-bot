"""Konsey aksiyonlari 1/4/5: SPY kiyasi, arsiv saklama+budama, kalite metrikleri."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np

from app.config.settings import Settings
from app.scheduler import Scheduler
from app.services.database import Database
from app.services.gist_backup import GistBackup
from app.services.market_calendar import MarketCalendar
from app.services.signal_tracker import SignalTracker
from app.services.state_store import InMemoryStateStore
from tests import fixtures as fx
from tests.test_gist_backup import FakeGistClient
from tests.test_scheduler import FakeNotifier


def _tracker(tmp_path):
    return SignalTracker(Database(str(tmp_path / "c.db")), "1h")


def _sig(db, symbol, status="FILLED", closed_utc=None, created="2026-07-29T14:00:00Z",
         fill=101.0):
    db.execute(
        "INSERT INTO signals(symbol,direction,created_utc,entry_candle_ts,"
        "entry_min,entry_max,stop_loss,tp1,tp2,rr,status,outcome,closed_utc,"
        "fill_price) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (symbol, "LONG", created, 1000, 100.0, 101.0, 98.0, 106.0, 110.0,
         2.5, status, "WIN" if status == "CLOSED" else None, closed_utc,
         fill if status in ("FILLED", "CLOSED") else None))


def test_benchmark_spy_same_period(tmp_path):
    tracker = _tracker(tmp_path)
    _sig(tracker._db, "AAPL", created="2026-07-20T14:00:00Z")
    settings = Settings(TELEGRAM_ENABLED=False, STATE_BACKEND="memory")
    sched = Scheduler(settings, None, None, None, MarketCalendar(),
                      InMemoryStateStore(), FakeNotifier(), tracker)
    spy = fx.make_series(np.linspace(100, 110, 30), symbol="SPY", interval="1d")
    sched._daily_cache = {"SPY": spy}
    sched._daily_cache_date = sched._calendar.now_et().date()
    b = sched.benchmark_info()
    assert b is not None and b["since"] == "2026-07-20"
    assert b["spy_return_pct"] > 0


def test_archive_symbols_retention(tmp_path):
    tracker = _tracker(tmp_path)
    now = datetime.now(timezone.utc)
    _sig(tracker._db, "OPEN1", status="FILLED")
    _sig(tracker._db, "FRESH", status="CLOSED",
         closed_utc=(now - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    _sig(tracker._db, "STALE", status="CLOSED",
         closed_utc=(now - timedelta(days=45)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    syms = tracker.archive_symbols(retention_days=30)
    assert "OPEN1" in syms and "FRESH" in syms and "STALE" not in syms


def test_gist_prune_deletes_stale_candles(tmp_path):
    tracker = _tracker(tmp_path)
    _sig(tracker._db, "AAPL", status="FILLED")
    client = FakeGistClient()
    backup = GistBackup(client, tracker)
    backup.sync()                                  # gist olusur
    gid = backup._gist_id
    # gist'te saklama disi kalan eski bir mum dosyasi varmis gibi yap
    client.store[gid]["files"]["candles_OLD_1d.csv"] = "ts,open\n1,2"
    backup._last_sync = 0
    backup.sync()
    assert "candles_OLD_1d.csv" not in client.store[gid]["files"]   # budandi


def test_fill_quality_mfe_mae(tmp_path):
    tracker = _tracker(tmp_path)
    _sig(tracker._db, "AAPL", status="FILLED", fill=101.0)
    closes = np.array([102.0, 104.0, 100.0, 103.0])
    series = fx.make_series(closes, symbol="AAPL")
    for i, c in enumerate(series.candles):
        c.ts = 2000 + i * 3_600_000
        c.high = c.close + 0.5
        c.low = c.close - 0.5
    tracker.record_candles(series)
    fq = tracker.fill_quality()
    assert fq["n"] == 1
    # risk=3; MFE=(104.5-101)/3=+1.17R  MAE=(99.5-101)/3=-0.5R
    assert abs(fq["per"][0]["mfe_r"] - 1.17) < 0.02
    assert abs(fq["per"][0]["mae_r"] + 0.5) < 0.02


def test_eod_extras_text(tmp_path):
    tracker = _tracker(tmp_path)
    _sig(tracker._db, "AAPL", status="FILLED")
    settings = Settings(TELEGRAM_ENABLED=False, STATE_BACKEND="memory")
    sched = Scheduler(settings, None, None, None, MarketCalendar(),
                      InMemoryStateStore(), FakeNotifier(), tracker)
    spy = fx.make_series(np.linspace(100, 105, 30), symbol="SPY", interval="1d")
    sched._daily_cache = {"SPY": spy}
    sched._daily_cache_date = sched._calendar.now_et().date()
    txt = sched.build_eod_extras()
    assert "SPY ayni donem" in txt and "Setup dagilimi" in txt
