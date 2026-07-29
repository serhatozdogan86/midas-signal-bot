"""CommentaryService + market_report testleri (deterministik sablonlar)."""
from __future__ import annotations

import numpy as np

from app.services import market_report
from app.services.commentary import CommentaryService
from app.services.database import Database
from app.services.signal_tracker import SignalTracker
from tests import fixtures as fx


# ---------------------------------------------------------------- commentary
def _tracker(tmp_path):
    return SignalTracker(Database(str(tmp_path / "c.db")), "1h")


def test_commentary_empty_state(tmp_path):
    tracker = _tracker(tmp_path)
    svc = CommentaryService(tracker._db, tracker)
    row = svc.generate("BULL")
    assert "Henuz sonuclanan sinyal yok" in row["text"]
    assert "golge muhasebe" in row["text"]
    assert svc.latest()["text"] == row["text"]


def test_commentary_with_results_and_gap_warning(tmp_path):
    tracker = _tracker(tmp_path)
    db = tracker._db
    rows = [
        ("AAPL", "LONG", "WIN", 1.7, "2026-07-28T20:00:00Z"),
        ("MSFT", "LONG", "LOSS", -2.1, "2026-07-28T21:00:00Z"),  # gap kaybi
        ("XYZ", "SHORT", "WIN", 1.2, "2026-07-28T22:00:00Z"),
    ]
    for i, (sym, direction, outcome, r, closed) in enumerate(rows):
        db.execute(
            "INSERT INTO signals(symbol,direction,created_utc,entry_candle_ts,"
            "entry_min,entry_max,stop_loss,tp1,tp2,rr,status,outcome,"
            "r_multiple,closed_utc) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (sym, direction, f"2026-07-28T1{i}:00:00Z", 1000 + i,
             100.0, 101.0, 98.0, 106.0, 110.0, 2.5, "CLOSED", outcome,
             r, closed))
    svc = CommentaryService(db, tracker)
    text = svc.generate("BULL")["text"]
    assert "3 sonuclanan sinyal" in text and "isabet %66.7" in text
    assert "Gap uyarisi" in text and "MSFT" in text          # r < -1.3
    assert "Yon bilancosu" in text and "guncel rejim: BULL" in text
    assert "Orneklem hala kucuk (n=3)" in text

    # ikinci uretimde delta cumlesi
    text2 = svc.generate("BULL")["text"]
    assert "yeni sonuc yok" in text2
    assert len(svc.recent(10)) == 2


# -------------------------------------------------------------- market report
def _daily_map():
    mk = lambda c, s: fx.make_series(c, symbol=s, interval="1d", spread=0.02)
    return {
        "SPY": mk(fx.daily_uptrend_closes(), "SPY"),
        "QQQ": mk(fx.daily_uptrend_closes(), "QQQ"),
        "AAA": mk(fx.daily_uptrend_closes(), "AAA"),       # lider + 50MA ustu
        "BBB": mk(fx.daily_steep_downtrend_closes(), "BBB"),  # zayif
    }


def test_market_snapshot_and_note():
    snap = market_report.build_market_snapshot(
        _daily_map(), ["AAA", "BBB"], "BULL", earnings_blackout_count=3)
    assert snap["spy_change_pct"] is not None
    assert snap["breadth_sample"] == 2
    assert snap["breadth_above_50ma_pct"] == 50.0          # AAA ustte, BBB altta
    assert snap["rs_leaders"][0]["symbol"] == "AAA"
    assert snap["rs_laggards"][0]["symbol"] == "BBB"

    note = market_report.render_market_note(snap)
    assert "Gunluk piyasa notu (BULL rejimi)" in note
    assert "SPY" in note and "Genislik" in note
    assert "RS liderleri: AAA" in note
    assert "Bilanco blackout: 3 sembol" in note
    assert "yalniz LONG taranir" in note


def test_market_note_unknown_regime():
    note = market_report.render_market_note(
        {"regime": "UNKNOWN", "spy_change_pct": None})
    assert "rejim belirsiz" in note
