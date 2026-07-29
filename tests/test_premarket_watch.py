"""Premarket gap nobeti testleri - saf rapor fonksiyonu + scheduler tetigi."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.premarket_watch import build_gap_report, render_gap_report

ET = ZoneInfo("America/New_York")


def _sig(symbol="AAPL", direction="LONG", status="FILLED",
         stop=98.0, tp1=106.0):
    return {"symbol": symbol, "direction": direction, "status": status,
            "stop_loss": stop, "tp1": tp1}


def test_gap_through_stop_long():
    r = build_gap_report([_sig()], [], {"AAPL": 96.5}, {"AAPL": 101.0})
    assert len(r["position_alerts"]) == 1
    assert "STOP'un" in r["position_alerts"][0]
    assert "LIMIT emirle cikisi" in r["position_alerts"][0]
    text = render_gap_report(r)
    assert text and "gap nobeti" in text and "AAPL" in text


def test_gap_through_stop_short():
    r = build_gap_report([_sig(direction="SHORT", stop=63.6, tp1=60.9)],
                         [], {"AAPL": 64.8}, {"AAPL": 62.5})
    assert len(r["position_alerts"]) == 1 and "STOP" in r["position_alerts"][0]


def test_favorable_tp_gap():
    r = build_gap_report([_sig()], [], {"AAPL": 108.0}, {"AAPL": 101.0})
    assert "TP1'in" in r["position_alerts"][0]
    assert "kar realizasyonu" in r["position_alerts"][0]


def test_pending_big_gap_warns():
    r = build_gap_report([_sig(status="PENDING")], [],
                         {"AAPL": 105.5}, {"AAPL": 100.0})
    assert "gecersizlesmis olabilir" in r["position_alerts"][0]


def test_candidate_gap_and_quiet_case():
    r = build_gap_report([], ["XYZ", "ABC"],
                         {"XYZ": 104.0, "ABC": 100.4},
                         {"XYZ": 100.0, "ABC": 100.0})
    assert len(r["candidate_alerts"]) == 1 and "XYZ" in r["candidate_alerts"][0]

    quiet = build_gap_report([_sig()], ["ABC"],
                             {"AAPL": 101.2, "ABC": 100.4},
                             {"AAPL": 101.0, "ABC": 100.0})
    assert render_gap_report(quiet) is None       # kayda deger sey yok -> sessiz


def test_scheduler_gap_watch_trigger(monkeypatch, tmp_path):
    """tick: hazirlik sonrasi, acilis-30dk penceresinde TEK kez tetiklenir."""
    from tests.test_scheduler import _scheduler, _instrument

    sched, _ = _scheduler()
    calls = _instrument(sched, monkeypatch)
    watch_calls = []

    def fake_watch(today):
        watch_calls.append(today)
        sched._gap_watch_date = today
    monkeypatch.setattr(sched, "run_gap_watch", fake_watch)

    day = (2026, 7, 28)
    sched.tick(datetime(*day, 8, 50, tzinfo=ET))    # prep
    sched.tick(datetime(*day, 8, 55, tzinfo=ET))    # pencere disi (09:00 oncesi)
    assert watch_calls == []
    sched.tick(datetime(*day, 9, 10, tzinfo=ET))    # pencere ici -> nobet
    sched.tick(datetime(*day, 9, 20, tzinfo=ET))    # tekrar etmez
    assert len(watch_calls) == 1
    assert calls[0] == "prep"
