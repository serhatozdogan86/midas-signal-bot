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


# ------------------- v3.9.3 regresyonlari: gecici engel / cift sayim
def test_transient_block_does_not_orphan_later_real_signal(tmp_path):
    """Kill-switch GECICIDIR. 17:00'de engellenen sinyal blocked=3 satiri
    birakir; 19:00'da endeks duzelince ayni sinyal IZLEMEYE ALINABILMELI.
    Eski dedup blocked satirini 'acik kayit' sayip sessizce atliyordu -
    Telegram'a gidiyor, deftere yazilmiyordu."""
    sched, tracker = _scheduler(tmp_path)
    mtf = fx.make_series(np.linspace(100, 102, 40), symbol="AAPL")
    d = _decision(symbol="AAPL")
    sched._index_pcts = lambda: (-1.2, None)          # 17:00 tape kotu
    block = sched._entry_block(d)
    assert block is not None and block[1] == BLOCKED_KILL_SWITCH
    tracker.track_blocked(d, mtf, block[0], block[1])
    sched._index_pcts = lambda: (-0.1, 0.2)           # 19:00 tape duzeldi
    assert sched._entry_block(d) is None
    assert tracker.maybe_track(d, mtf) is True        # ESKIDEN False idi
    assert tracker._db.query_one(
        "SELECT COUNT(*) n FROM signals WHERE symbol='AAPL' AND blocked=0")["n"] == 1


def test_no_hypothetical_row_while_real_signal_open(tmp_path):
    """Gercek acik sinyal varken ayni sembol+yon icin varsayimsal kohort
    satiri acilmaz (ayni pozisyon hem karnede hem hypo_r'da sayilmasin)."""
    sched, tracker = _scheduler(tmp_path)
    mtf = fx.make_series(np.linspace(100, 102, 40), symbol="MSFT")
    d = _decision(symbol="MSFT")
    assert tracker.maybe_track(d, mtf) is True
    assert tracker.track_blocked(d, mtf, "kill-switch", BLOCKED_KILL_SWITCH) is False
    assert tracker.blocked_summary()["total"] == 0


# ------------------------------- v3.9.4: NaN korumasi + yonetim ucu kilidi
def test_plan_rejects_non_finite_values():
    """DIS INCELEME BULGUSU: NaN karsilastirmalari hep False doner ->
    RR/maliyet filtreleri NaN'i gecirir, NaN hedefli SIGNAL uretilirdi."""
    import numpy as _np
    import pandas as pd
    from app.config.settings import Settings as _S
    from app.models.decision import SetupType as _ST
    from app.strategies.risk_manager import SetupCandidate, build_trade_plan
    h = pd.DataFrame({"open": [100.0] * 40, "high": [101.0] * 40,
                      "low": [99.0] * 40, "close": [100.0] * 40,
                      "volume": [1e6] * 40})
    h.loc[39, "close"] = _np.nan
    n = 60
    d = pd.DataFrame({"open": [100.0] * n,
                      "high": [101.0 + i * 0.1 for i in range(n)],
                      "low": [99.0] * n,
                      "close": [100.0 + i * 0.1 for i in range(n)],
                      "volume": [1e6] * n})
    sc = SetupCandidate(setup_type=_ST.BREAKOUT_RETEST, level=100.0,
                        note="", event_index=30)
    assert build_trade_plan(h, d, Direction.LONG, sc,
                            _S().strategy_params) is None


def _client(tmp_path, token=""):
    from app.server import create_app
    from app.services.universe import UniverseProvider
    sched, tracker = _scheduler(tmp_path)
    sched._settings = Settings(TELEGRAM_ENABLED=False, STATE_BACKEND="memory",
                               ADMIN_TOKEN=token)
    app = create_app(InMemoryStateStore(), sched,
                     UniverseProvider.__new__(UniverseProvider), tracker)
    return app.test_client()


def test_scan_endpoint_locked_without_token(tmp_path):
    """GET /scan TAM TARAMA tetikler + Telegram'a sinyal gonderir.
    Token yoksa 503 (guvenli varsayilan), yanlis token 401."""
    assert _client(tmp_path).get("/scan").status_code == 503
    c = _client(tmp_path, token="s3cret")
    assert c.get("/scan?token=yanlis").status_code == 401
    assert c.get("/scan/dry?token=yanlis").status_code == 401
    assert c.post("/backup/now").status_code == 401      # token var, verilmedi
    assert _client(tmp_path).post("/backup/now").status_code == 503


def test_wallet_rows_are_capped(tmp_path):
    c = _client(tmp_path)
    rows = [{"s": "AAPL", "q": 1, "e": 100.0} for _ in range(500)]
    r = c.post("/wallet", json={"rows": rows})
    assert r.status_code == 200 and r.get_json()["count"] <= 200


# ---------------- v3.10: giris bolgesi gercekciligi (29 Tem GM vakasi)
def _plan(level, close, daily_slope=0.1, n=60, direction=None,
          zone_atr=0.5, tp1_r=0.5):
    """level ve son 1h kapanis verilerek plan kurar (bolge = sorted(level, close))."""
    import pandas as pd
    from app.config.settings import Settings as _S
    from app.models.decision import SetupType as _ST
    from app.strategies.risk_manager import SetupCandidate, build_trade_plan
    # saatlik taban yeterince asagida olmali; aksi halde YAPISAL STOP
    # giris ortasina oturur, risk=0 cikar ve plan bizim korumalarimiza
    # GELMEDEN duser (ilk kurgumun hatasi - kural test edilmemis olurdu).
    h = pd.DataFrame({"open": [close] * 40, "high": [close + 0.5] * 40,
                      "low": [close - 4.0] * 40, "close": [close] * 40,
                      "volume": [1e6] * 40})
    d = pd.DataFrame({"open": [100.0] * n,
                      "high": [100.0 + i * daily_slope + 1 for i in range(n)],
                      "low": [100.0 + i * daily_slope - 1 for i in range(n)],
                      "close": [100.0 + i * daily_slope for i in range(n)],
                      "volume": [1e6] * n})
    p = _S(MAX_ENTRY_ZONE_ATR=zone_atr,
           WORST_FILL_TP1_R_MIN=tp1_r).strategy_params
    sc = SetupCandidate(setup_type=_ST.BREAKOUT_RETEST, level=level,
                        note="", event_index=30)
    return build_trade_plan(h, d, direction or Direction.LONG, sc, p)


def test_wide_entry_zone_is_rejected():
    """GM vakasi: bolge 84.33-91.04 (~%8) -> plan kurulmamali."""
    assert _plan(level=84.33, close=91.04) is None


def test_narrow_entry_zone_still_produces_plan():
    plan = _plan(level=100.3, close=100.0)
    assert plan is not None and plan.entry_max - plan.entry_min < 0.5


def test_zone_cap_is_configurable_and_binding():
    # ayni girdi: dar tavanda red, gevsek tavanda kabul
    assert _plan(level=98.0, close=100.0, zone_atr=0.05) is None
    assert _plan(level=98.0, close=100.0, zone_atr=5.0, tp1_r=-99) is not None


def test_worst_fill_tp1_guard_blocks_negative_edge():
    """En kotu dolumda (LONG: entry_max) TP1 kazanci esigin altindaysa red.
    tp1_r esigi cok yuksek tutuldugunda gecerli plan bile reddedilmeli -
    kuralin BAGLAYICI oldugunu kanitlar (sessizce gecmiyor)."""
    assert _plan(level=100.3, close=100.0, tp1_r=5.0) is None
    assert _plan(level=100.3, close=100.0, tp1_r=0.0) is not None


# ------------------------- v3.11: evren bayatlik alarmi (31 Tem sessizligi)
def test_universe_refresh_empty_keeps_old_list_and_warns(caplog):
    """Likidite filtresi bos donerse eski liste servis edilir ama tarih
    GUNCELLENMEZ -> sessiz bayatlama. Artik WARNING loglanir."""
    from datetime import date, timedelta
    from app.services.universe import UniverseProvider
    u = UniverseProvider.__new__(UniverseProvider)
    import threading
    u._lock = threading.Lock()
    u._filtered = ["AAPL", "MSFT"]
    u._filtered_date = date.today() - timedelta(days=3)
    u._raw_count = 0
    u._load_raw = lambda: ["AAPL", "MSFT"]
    u._liquidity_filter = lambda raw: []          # filtre coktu
    with caplog.at_level("WARNING"):
        out = u.refresh()
    assert out == []
    assert u._filtered == ["AAPL", "MSFT"]        # eski liste korunur
    assert any("universe_refresh_empty" in r.message for r in caplog.records)
    assert u.stale_days() == 3


def test_universe_stale_days_zero_when_fresh():
    from datetime import date
    from app.services.universe import UniverseProvider
    import threading
    u = UniverseProvider.__new__(UniverseProvider)
    u._lock = threading.Lock()
    u._filtered = ["AAPL"]
    u._filtered_date = date.today()
    assert u.stale_days() == 0


def test_open_blackout_blocks_pre_market_by_design():
    """Acilis oncesi (negatif dakika) breakout tetigi KAPALI - bilincli.
    Bu davranis 3 Agu'da test_fine_scan'i kirdi (test seans oncesi
    kosuyordu); uretimde ince tarama yalniz seans icinde calistigi icin
    etki yok, ama kural burada acikca kilitlenir."""
    assert in_open_blackout(-300.0, 30) is True
    assert in_open_blackout(-1.0, 30) is True
