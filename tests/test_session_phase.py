"""Seans fazi etiketleme testleri (2 Agu - kohort analizi icin veri toplama)."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.market_calendar import (
    PHASE_AFTER, PHASE_AFTERNOON, PHASE_CLOSED, PHASE_LUNCH, PHASE_MORNING,
    PHASE_OPEN, PHASE_POWER, PHASE_PRE, MarketCalendar,
)

ET = ZoneInfo("America/New_York")


def _et(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=ET)


def test_normal_trading_day_phases():
    """2026-08-03 Pazartesi, normal seans (09:30-16:00 ET)."""
    cal = MarketCalendar()
    cases = [
        (_et(2026, 8, 3, 3, 30), PHASE_CLOSED),     # pre-market bile degil
        (_et(2026, 8, 3, 7, 0), PHASE_PRE),
        (_et(2026, 8, 3, 9, 29), PHASE_PRE),
        (_et(2026, 8, 3, 9, 30), PHASE_OPEN),       # acilis ani
        (_et(2026, 8, 3, 9, 59), PHASE_OPEN),
        (_et(2026, 8, 3, 10, 0), PHASE_MORNING),    # ilk 30 dk bitti
        (_et(2026, 8, 3, 11, 59), PHASE_MORNING),
        (_et(2026, 8, 3, 12, 0), PHASE_LUNCH),
        (_et(2026, 8, 3, 13, 59), PHASE_LUNCH),
        (_et(2026, 8, 3, 14, 0), PHASE_AFTERNOON),
        (_et(2026, 8, 3, 14, 59), PHASE_AFTERNOON),
        (_et(2026, 8, 3, 15, 0), PHASE_POWER),      # son saat
        (_et(2026, 8, 3, 15, 59), PHASE_POWER),
        (_et(2026, 8, 3, 16, 0), PHASE_AFTER),      # kapanis
        (_et(2026, 8, 3, 19, 59), PHASE_AFTER),
        (_et(2026, 8, 3, 20, 0), PHASE_CLOSED),     # after-hours bitti
    ]
    for dt, expected in cases:
        assert cal.session_phase(dt) == expected, f"{dt} -> {expected}"


def test_weekend_and_holiday_are_closed():
    cal = MarketCalendar()
    assert cal.session_phase(_et(2026, 8, 1, 12, 0)) == PHASE_CLOSED   # Cumartesi
    assert cal.session_phase(_et(2026, 8, 2, 12, 0)) == PHASE_CLOSED   # Pazar
    assert cal.session_phase(_et(2026, 12, 25, 12, 0)) == PHASE_CLOSED  # Noel


def test_early_close_day_power_hour_shifts():
    """Erken kapanis (13:00 ET): son saat 12:00-13:00'e KAYAR ve
    kapanis sonrasi after-hours baslar."""
    cal = MarketCalendar()
    d = (2026, 11, 27)                       # NYSE erken kapanis gunu
    assert cal.session_phase(_et(*d, 9, 45)) == PHASE_OPEN
    assert cal.session_phase(_et(*d, 11, 0)) == PHASE_MORNING
    assert cal.session_phase(_et(*d, 12, 30)) == PHASE_POWER   # ogle degil!
    assert cal.session_phase(_et(*d, 13, 0)) == PHASE_AFTER    # erken kapanis
    assert cal.session_phase(_et(*d, 15, 0)) == PHASE_AFTER


def test_accepts_utc_input_and_converts():
    """UTC (veya baska dilim) verilen an ET'ye cevrilerek siniflandirilir."""
    from datetime import timezone
    cal = MarketCalendar()
    # 2026-08-03 14:00 UTC = 10:00 ET (yaz saati, UTC-4) -> MORNING
    utc_dt = datetime(2026, 8, 3, 14, 0, tzinfo=timezone.utc)
    assert cal.session_phase(utc_dt) == PHASE_MORNING


def test_default_uses_now():
    """Parametresiz cagri patlamamali ve gecerli bir faz dondurmeli."""
    cal = MarketCalendar()
    phase = cal.session_phase()
    assert phase in {PHASE_PRE, PHASE_OPEN, PHASE_MORNING, PHASE_LUNCH,
                     PHASE_AFTERNOON, PHASE_POWER, PHASE_AFTER, PHASE_CLOSED}


def test_phase_breakdown_groups_by_phase(tmp_path):
    """Kapanan sinyaller contract_json'daki faza gore gruplanir; eski
    (fazsiz) kayitlar BILINMIYOR altinda toplanir."""
    import json as _json

    from app.services.database import Database
    from app.services.signal_tracker import SignalTracker

    tracker = SignalTracker(Database(str(tmp_path / "p.db")), "1h")

    def _closed(symbol, phase, r):
        contract = _json.dumps({"session_phase": phase}) if phase else None
        tracker._db.execute(
            "INSERT INTO signals(symbol,direction,created_utc,entry_candle_ts,"
            "entry_min,entry_max,stop_loss,tp1,tp2,rr,status,outcome,"
            "r_multiple,closed_utc,fill_price,contract_json,blocked) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)",
            (symbol, "LONG", "2026-08-03T14:00:00Z", 1, 100, 101, 98, 106, 110,
             2.5, "CLOSED", "WIN" if r > 0 else "LOSS", r,
             "2026-08-04T20:00:00Z", 100.5, contract))

    _closed("A", "OPENING_RANGE", 1.5)
    _closed("B", "OPENING_RANGE", -1.0)
    _closed("C", "LUNCH", -1.0)
    _closed("D", None, 2.0)               # eski kayit (faz yok)

    out = {b["phase"]: b for b in tracker.phase_breakdown()}
    assert out["OPENING_RANGE"]["n"] == 2
    assert out["OPENING_RANGE"]["wins"] == 1
    assert out["OPENING_RANGE"]["win_rate"] == 0.5
    assert out["LUNCH"]["n"] == 1
    assert out["BILINMIYOR"]["n"] == 1
    # net beklenti brutten kucuk olmali (komisyon dusulur)
    assert out["OPENING_RANGE"]["net_r"] < out["OPENING_RANGE"]["gross_r"]


def test_decision_carries_session_phase():
    """Decision modeli fazi tasiyabilmeli (scheduler damgalar)."""
    from app.models.decision import Decision
    d = Decision.base("AAPL", "1d", "1h")
    assert d.session_phase is None
    d.session_phase = "POWER_HOUR"
    assert d.contract_dict()["session_phase"] == "POWER_HOUR"
