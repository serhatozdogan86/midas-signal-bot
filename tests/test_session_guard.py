"""v3.9 seans korumasi testleri (29 Tem otopsisi):
1) index_kill_switch saf kural - sinir degerler + yon asimetrisi + fail-open
2) in_open_blackout saf kural - pencere sinirlari
3) _entry_block entegrasyonu - siniflar (3/4/2) ve oncelik sirasi
4) track_blocked - sinif bazli kayit + blocked_summary by_class
5) REGRESYON: cift kayit bug'i - tavana takilan sinyal karneye sizamaz;
   tavan sayimi sinyalin kendi satirini saymaz ("tavan 3" = 3'e izin)
"""
from __future__ import annotations

import numpy as np

from app.config.settings import Settings
from app.models.decision import (Confidence, Decision, Direction,
                                 EntryZone, SetupType, Targets, TimeFrames)
from app.models.decision import DecisionType
from app.scheduler import Scheduler
from app.services.database import Database
from app.services.market_calendar import MarketCalendar
from app.services.signal_tracker import SignalTracker
from app.services.state_store import InMemoryStateStore
from app.strategies.session_guard import (
    BLOCKED_KILL_SWITCH, BLOCKED_OPEN_BLACKOUT, BLOCKED_PORTFOLIO,
    in_open_blackout, index_kill_switch)
from tests import fixtures as fx
from tests.test_scheduler import FakeNotifier


# ------------------------------------------------- 1) kill-switch saf kural
def test_kill_switch_long_spy_boundary():
    # esik 0.75: -0.75 SINIRDA engellenir, -0.74 serbest
    assert not index_kill_switch("LONG", -0.75, 0.0, 0.75, 1.0).allowed
    assert index_kill_switch("LONG", -0.74, 0.0, 0.75, 1.0).allowed


def test_kill_switch_long_qqq_leg():
    v = index_kill_switch("LONG", -0.10, -1.0, 0.75, 1.0)
    assert not v.allowed and "QQQ" in v.reason


def test_kill_switch_short_mirror():
    # SHORT: guclu YUKARI tape engeller, dusus engellemez
    assert not index_kill_switch("SHORT", 0.75, 0.0, 0.75, 1.0).allowed
    assert index_kill_switch("SHORT", -5.0, -5.0, 0.75, 1.0).allowed


def test_kill_switch_fail_open_when_no_data():
    assert index_kill_switch("LONG", None, None, 0.75, 1.0).allowed


def test_kill_switch_partial_data_still_blocks():
    # SPY verisi yok ama QQQ esigi asmis -> engellenir
    assert not index_kill_switch("LONG", None, -1.2, 0.75, 1.0).allowed


def test_kill_switch_threshold_sign_agnostic():
    # esikler buyukluk olarak yorumlanir (negatif verilse de ayni sonuc)
    assert not index_kill_switch("LONG", -0.8, 0.0, -0.75, -1.0).allowed


# --------------------------------------------- 2) acilis penceresi saf kural
def test_open_blackout_window():
    assert in_open_blackout(0.0, 30)
    assert in_open_blackout(29.9, 30)
    assert not in_open_blackout(30.0, 30)
    assert not in_open_blackout(45.0, 30)


def test_open_blackout_pre_open_and_disabled():
    assert in_open_blackout(-5.0, 30)        # acilis oncesi manuel cagri
    assert not in_open_blackout(10.0, 0)     # 0 dk = ozellik kapali
    assert not in_open_blackout(None, 30)    # seans yok -> fail-open


# ----------------------------------------------------- ortak test iskeleti
def _decision(setup=SetupType.BREAKOUT_RETEST,
              direction=Direction.LONG, symbol="AAPL") -> Decision:
    return Decision(
        symbol=symbol, timestamp_utc="2026-08-03T14:00:00Z",
        timeframes=TimeFrames(htf="1d", mtf="1h"),
        decision=DecisionType.SIGNAL, direction=direction,
        setup_type=setup, confidence=Confidence.MEDIUM,
        entry_zone=EntryZone(min=100.0, max=101.0), stop_loss=98.0,
        targets=Targets(tp1=106.0, tp2=110.0), rr=2.5,
        time_stop_date="2026-08-07")


def _scheduler(tmp_path, **env) -> tuple[Scheduler, SignalTracker]:
    tracker = SignalTracker(Database(str(tmp_path / "g.db")), "1h")
    settings = Settings(TELEGRAM_ENABLED=False, STATE_BACKEND="memory", **env)
    sched = Scheduler(settings, None, None, None, MarketCalendar(),
                      InMemoryStateStore(), FakeNotifier(), tracker)
    # deterministik test: endeks verisi ve saat disaridan enjekte edilir
    sched._index_pcts = lambda: (None, None)
    sched._minutes_since_open = lambda now_et=None: 120.0
    return sched, tracker


# --------------------------------------- 3) _entry_block sinif ve oncelik
def test_entry_block_kill_switch_class(tmp_path):
    sched, _ = _scheduler(tmp_path)
    sched._index_pcts = lambda: (-1.2, -0.3)
    block = sched._entry_block(_decision())
    assert block is not None
    reason, cls = block
    assert cls == BLOCKED_KILL_SWITCH and "SPY" in reason


def test_entry_block_short_allowed_on_down_tape(tmp_path):
    sched, _ = _scheduler(tmp_path)
    sched._index_pcts = lambda: (-1.2, -2.0)
    assert sched._entry_block(_decision(direction=Direction.SHORT)) is None


def test_entry_block_open_blackout_breakout_only(tmp_path):
    sched, _ = _scheduler(tmp_path)
    sched._minutes_since_open = lambda now_et=None: 10.0
    block = sched._entry_block(_decision(setup=SetupType.BREAKOUT_RETEST))
    assert block is not None and block[1] == BLOCKED_OPEN_BLACKOUT
    # pullback sinyali pencereden ETKILENMEZ
    assert sched._entry_block(_decision(setup=SetupType.TREND_PULLBACK)) is None


def test_entry_block_kill_switch_disabled(tmp_path):
    sched, _ = _scheduler(tmp_path, INDEX_KILL_SWITCH_ENABLED=False)
    sched._index_pcts = lambda: (-3.0, -3.0)
    assert sched._entry_block(_decision()) is None


def test_entry_block_priority_kill_switch_over_blackout(tmp_path):
    sched, _ = _scheduler(tmp_path)
    sched._index_pcts = lambda: (-1.2, None)
    sched._minutes_since_open = lambda now_et=None: 5.0
    block = sched._entry_block(_decision())
    assert block is not None and block[1] == BLOCKED_KILL_SWITCH


# ------------------------------- 4) track_blocked siniflari + by_class
def test_track_blocked_classes_and_summary(tmp_path):
    sched, tracker = _scheduler(tmp_path)
    mtf = fx.make_series(np.linspace(100, 102, 40), symbol="AAPL")
    assert tracker.track_blocked(_decision(), mtf, "endeks kill-switch (SPY -1.20%)",
                                 BLOCKED_KILL_SWITCH)
    assert tracker.track_blocked(_decision(symbol="MSFT"), mtf,
                                 "acilis penceresi", BLOCKED_OPEN_BLACKOUT)
    # ayni sembol+yon+sinif tekrar kaydedilmez (dedup)
    assert not tracker.track_blocked(_decision(), mtf, "tekrar",
                                     BLOCKED_KILL_SWITCH)
    summary = tracker.blocked_summary()
    assert summary["total"] == 2
    assert summary["by_class"][str(BLOCKED_KILL_SWITCH)]["n"] == 1
    assert summary["by_class"][str(BLOCKED_OPEN_BLACKOUT)]["n"] == 1
    # blocked satirlar karne sorgusuna girmez
    assert tracker.stats()["decided_trades"] == 0


def test_blocked_rows_never_enter_scorecard(tmp_path):
    # blocked=3 satiri kapansa bile karneye degil hypo_r'a yazilir
    sched, tracker = _scheduler(tmp_path)
    mtf = fx.make_series(np.linspace(100, 102, 40), symbol="NVDA")
    tracker.track_blocked(_decision(symbol="NVDA"), mtf, "ks",
                          BLOCKED_KILL_SWITCH)
    tracker._db.execute(
        "UPDATE signals SET status='CLOSED', outcome='LOSS', r_multiple=-1.0 "
        "WHERE symbol='NVDA'")
    assert tracker.stats()["decided_trades"] == 0
    assert tracker.blocked_summary()["by_class"][
        str(BLOCKED_KILL_SWITCH)]["hypo_r"] == -1.0


# --------------------------- 5) cift kayit regresyonu + tavan semantigi
def test_cluster_cap_allows_limit_blocks_next(tmp_path):
    """'kume tavani 3' = 3 sinyale IZIN verir, 4.su blocked=2 olur.
    Eski bug: sayim maybe_track'ten SONRA yapildigi icin sinyal kendi
    satirini sayiyor ve 3.su yanlislikla engelleniyordu."""
    sched, tracker = _scheduler(tmp_path)
    mtf = fx.make_series(np.linspace(100, 102, 40))
    # ayni kume (LONG + ayni gun): ilk 3 giris serbest olmali
    for i, sym in enumerate(("AAA", "BBB", "CCC")):
        d = _decision(symbol=sym, setup=SetupType.TREND_PULLBACK)
        assert sched._entry_block(d) is None, f"{i+1}. sinyal engellenmemeli"
        assert tracker.maybe_track(d, fx.make_series(
            np.linspace(100, 102, 40), symbol=sym))
    d4 = _decision(symbol="DDD", setup=SetupType.TREND_PULLBACK)
    block = sched._entry_block(d4)
    assert block is not None and block[1] == BLOCKED_PORTFOLIO
    assert "kume" in block[0]
    tracker.track_blocked(d4, mtf, block[0], block[1])
    # REGRESYON cekirdegi: DDD icin blocked=0 satir YOK, tek satir blocked=2
    rows = tracker._db.query(
        "SELECT blocked, COUNT(*) n FROM signals WHERE symbol='DDD' "
        "GROUP BY blocked")
    assert len(rows) == 1 and rows[0]["blocked"] == 2 and rows[0]["n"] == 1
    # karne sayimi: yalniz 3 gercek sinyal
    assert tracker._db.query_one(
        "SELECT COUNT(*) n FROM signals WHERE blocked=0")["n"] == 3


def test_guard_info_shape(tmp_path):
    sched, _ = _scheduler(tmp_path)
    sched._index_pcts = lambda: (-0.9, 0.1)
    sched._minutes_since_open = lambda now_et=None: 12.0
    info = sched.guard_info()
    assert info["kill_switch"]["long_blocked"] is True
    assert info["kill_switch"]["short_blocked"] is False
    assert info["open_blackout"]["active"] is True
