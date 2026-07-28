"""SignalTracker - golge takip sonuclandirma testleri (gap muhasebesi dahil)."""
from __future__ import annotations

import numpy as np

from app.models.decision import (
    Decision, DecisionType, Direction, EntryZone, Targets, TimeFrames,
)
from app.services.database import Database
from app.services.signal_tracker import SignalTracker
from tests import fixtures as fx


def _make_tracker(tmp_path, fill_window=14, max_track=28):
    db = Database(str(tmp_path / "test.db"))
    return SignalTracker(db, mtf_interval="1h",
                         fill_window_bars=fill_window,
                         max_track_bars=max_track), db


def _signal(symbol="AAPL", direction=Direction.LONG,
            entry=(100.0, 101.0), stop=98.0, tp1=106.0, tp2=110.0) -> Decision:
    return Decision(
        symbol=symbol, timestamp_utc="2026-07-27T00:00:00Z",
        timeframes=TimeFrames(htf="1d", mtf="1h"),
        decision=DecisionType.SIGNAL, direction=direction,
        entry_zone=EntryZone(min=entry[0], max=entry[1]),
        stop_loss=stop, targets=Targets(tp1=tp1, tp2=tp2), rr=2.5,
        time_stop_date="2026-07-31")


def _track(tracker, d, last_ts=1_000_000):
    mtf = fx.make_series(np.full(70, 102.0), symbol=d.symbol)
    mtf.candles[-1].ts = last_ts
    assert tracker.maybe_track(d, mtf) is True


def _feed(tracker, bars, symbol="AAPL", start_ts=1_000_001):
    """bars: [(open, high, low, close), ...] deterministik 1h mumlar."""
    series = fx.make_series(
        np.array([b[3] for b in bars] + [bars[-1][3]]), symbol=symbol)
    for i, c in enumerate(series.candles[:-1]):
        o, h, l, cl = bars[i]
        c.ts = start_ts + i * 3_600_000
        c.open, c.high, c.low, c.close = float(o), float(h), float(l), float(cl)
    tracker.record_candles(series)


def test_win_path(tmp_path):
    tracker, _ = _make_tracker(tmp_path)
    _track(tracker, _signal())
    # bar0: low 100.5 <= entry_max 101 -> FILLED @101 (gap yok)
    # bar2: high 106.5 >= tp1 106 -> WIN, r = (106-101)/(101-98) = 1.67
    _feed(tracker, [(102.0, 102.5, 100.5, 101.2),
                    (101.2, 103.0, 101.0, 102.8),
                    (102.8, 106.5, 102.5, 106.2)])
    tracker.evaluate_open("AAPL")
    sig = tracker.recent_signals(1)[0]
    assert sig["status"] == "CLOSED" and sig["outcome"] == "WIN"
    assert abs(sig["r_multiple"] - 1.67) < 0.01
    assert tracker.stats()["win_rate"] == 1.0


def test_loss_path(tmp_path):
    tracker, _ = _make_tracker(tmp_path)
    _track(tracker, _signal())
    _feed(tracker, [(102.0, 102.5, 100.8, 101.2),   # FILLED @101
                    (101.2, 101.5, 97.8, 98.2)])    # low <= stop 98 -> LOSS -1R
    tracker.evaluate_open("AAPL")
    sig = tracker.recent_signals(1)[0]
    assert sig["outcome"] == "LOSS" and sig["r_multiple"] == -1.0


def test_gap_through_stop_exits_at_open(tmp_path):
    """Gece gap'i stop'un ALTINDA acilis: cikis stop'tan degil ACILIS'tan.
    Kayip -1R'den derin olur (plan bolum 3: stop garantisi yok)."""
    tracker, _ = _make_tracker(tmp_path)
    _track(tracker, _signal())
    _feed(tracker, [(102.0, 102.5, 100.8, 101.2),   # FILLED @101, risk=3
                    (95.0, 96.0, 94.5, 95.5)])      # acilis 95 < stop 98
    tracker.evaluate_open("AAPL")
    sig = tracker.recent_signals(1)[0]
    assert sig["outcome"] == "LOSS"
    assert sig["exit_price"] == 95.0
    assert abs(sig["r_multiple"] - (-2.0)) < 0.01   # (95-101)/3


def test_gap_through_tp_exits_at_open(tmp_path):
    """Gap hedefin UZERINDE acilis: cikis acilistan (lehte)."""
    tracker, _ = _make_tracker(tmp_path)
    _track(tracker, _signal())
    _feed(tracker, [(102.0, 102.5, 100.8, 101.2),   # FILLED @101
                    (108.0, 109.0, 107.5, 108.5)])  # acilis 108 > tp1 106
    tracker.evaluate_open("AAPL")
    sig = tracker.recent_signals(1)[0]
    assert sig["outcome"] == "WIN"
    assert sig["exit_price"] == 108.0
    assert abs(sig["r_multiple"] - 2.33) < 0.01     # (108-101)/3


def test_not_filled_after_window(tmp_path):
    tracker, _ = _make_tracker(tmp_path, fill_window=3)
    _track(tracker, _signal())
    bars = [(103.0, 103.5, 102.0, 103.0)] * 3       # bolgeye hic inmez
    _feed(tracker, bars)
    tracker.evaluate_open("AAPL")
    sig = tracker.recent_signals(1)[0]
    assert sig["outcome"] == "NOT_FILLED"
    assert tracker.stats()["win_rate"] is None      # orana dahil degil


def test_ambiguous_same_bar(tmp_path):
    tracker, _ = _make_tracker(tmp_path)
    _track(tracker, _signal())
    _feed(tracker, [(102.0, 102.5, 100.8, 101.2),   # FILLED
                    (101.0, 106.5, 97.5, 100.0)])   # ayni barda stop + tp
    tracker.evaluate_open("AAPL")
    sig = tracker.recent_signals(1)[0]
    assert sig["outcome"] == "AMBIGUOUS" and sig["r_multiple"] == 0.0


def test_short_direction(tmp_path):
    tracker, _ = _make_tracker(tmp_path)
    _track(tracker, _signal(direction=Direction.SHORT,
                            entry=(62.4, 62.9), stop=63.6, tp1=60.9, tp2=59.1))
    # SHORT fill: high >= entry_min 62.4 -> fill @62.4; tp: low <= 60.9
    _feed(tracker, [(62.0, 62.6, 61.8, 62.2),
                    (62.2, 62.5, 60.7, 60.8)])
    tracker.evaluate_open("AAPL")
    sig = tracker.recent_signals(1)[0]
    assert sig["outcome"] == "WIN"
    assert abs(sig["r_multiple"] - 1.25) < 0.01     # (62.4-60.9)/(63.6-62.4)


def test_duplicate_open_signal_not_tracked(tmp_path):
    tracker, _ = _make_tracker(tmp_path)
    _track(tracker, _signal())
    mtf = fx.make_series(np.full(70, 102.0), symbol="AAPL")
    assert tracker.maybe_track(_signal(), mtf) is False


def test_expired_after_max_track(tmp_path):
    tracker, _ = _make_tracker(tmp_path, max_track=2)
    _track(tracker, _signal())
    bars = [(102.0, 102.5, 100.8, 101.2)] + [(101.5, 102.0, 101.0, 101.5)] * 3
    _feed(tracker, bars)
    tracker.evaluate_open("AAPL")
    sig = tracker.recent_signals(1)[0]
    assert sig["outcome"] == "EXPIRED"
    assert abs(sig["r_multiple"] - 0.17) < 0.01     # (101.5-101)/3


def test_decisions_and_candles_recorded(tmp_path):
    tracker, db = _make_tracker(tmp_path)
    d = _signal()
    tracker.record_decision(d)
    _feed(tracker, [(100.0, 101.0, 99.0, 100.5)] * 5)
    assert tracker.candles_count() == 5
    assert len(tracker.recent_decisions(10)) == 1
    assert tracker.stats()["dataset"]["decisions_recorded"] == 1
