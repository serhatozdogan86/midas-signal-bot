"""Faz 2 ince tarama testleri: bolge tetigi, kirilim tetigi, butce/cooldown."""
from __future__ import annotations

import numpy as np

from app.config.settings import Settings
from app.scheduler import Scheduler
from app.services.database import Database
from app.services.market_calendar import MarketCalendar
from app.services.signal_tracker import SignalTracker
from app.services.state_store import InMemoryStateStore
from tests import fixtures as fx
from tests.test_scheduler import FakeNotifier


class FineMD:
    def __init__(self, quotes, hourly=None):
        self.quotes = dict(quotes)
        self.hourly = hourly
        self.hourly_requests = []

    def get_quote(self, symbol):
        return self.quotes.get(symbol)

    def get_hourly_bulk(self, symbols):
        self.hourly_requests.append(list(symbols))
        return {s: self.hourly for s in symbols if self.hourly is not None}

    def get_daily_bulk(self, symbols, period=None):
        return {s: fx.make_series(fx.daily_uptrend_closes(), symbol=s,
                                  interval="1d", spread=0.02) for s in symbols}


def _sched(tmp_path, quotes, hourly=None, **kw):
    db = Database(str(tmp_path / "f.db"))
    tracker = SignalTracker(db, "1h")
    settings = Settings(TELEGRAM_ENABLED=True, STATE_BACKEND="memory", **kw)
    notifier = FakeNotifier()
    sched = Scheduler(settings, FineMD(quotes, hourly), None, None,
                      MarketCalendar(), InMemoryStateStore(), notifier, tracker)
    return sched, tracker, notifier, db


def _pending(db, symbol="LLY", lo=100.0, hi=101.0):
    db.execute(
        "INSERT INTO signals(symbol,direction,created_utc,entry_candle_ts,"
        "entry_min,entry_max,stop_loss,tp1,tp2,rr,status) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (symbol, "LONG", "2026-07-29T14:00:00Z", 0, lo, hi,
         98.0, 106.0, 110.0, 2.5, "PENDING"))


def test_zone_touch_notifies_once(tmp_path):
    sched, _, notifier, db = _sched(tmp_path, {"LLY": 100.4})
    _pending(db)
    sched.run_fine_scan()
    assert sched.last_fine_info["zone_hits"] == 1
    sched.run_fine_scan()      # ikinci turda tekrar bildirmez
    msgs = [m for m in notifier.sent if "GIRIS TETIKLENDI" in m]
    assert len(msgs) == 1 and "LLY" in msgs[0] and "LIMIT" in msgs[0]
    assert sched.last_fine_info["zone_hits"] == 0


def test_zone_not_touched_no_message(tmp_path):
    sched, _, notifier, db = _sched(tmp_path, {"LLY": 103.5})
    _pending(db)
    sched.run_fine_scan()
    assert notifier.sent == []


def test_breakout_trigger_reevaluates_and_signals(tmp_path):
    hourly = fx.make_series(fx.hourly_breakout_closes(),
                            volumes=fx.spike_volumes(178, spike_at=-1, mult=2.6))
    sched, tracker, notifier, _ = _sched(tmp_path, {"AAPL": 131.2}, hourly)
    # kaba taramanin biraktigi silahli aday + gunluk cache
    today = sched._calendar.now_et().date()
    sched._daily_cache = sched._md.get_daily_bulk(["AAPL", "SPY"])
    sched._daily_cache_date = today
    from app.models.decision import MarketRegime
    from app.strategies.regime_detector import RegimeResult
    sched._regime = RegimeResult(regime=MarketRegime.BULL)

    class FakeEarnings:
        def prefetch(self, symbols, today):
            return None

        def info(self, symbol, today, strict=True):
            from app.models.decision import EarningsInfo
            return EarningsInfo(next_date="2026-08-20", days_to=8)
    sched._earnings = FakeEarnings()
    sched._watchlist = [{"symbol": "AAPL", "state": "CANDIDATE",
                         "blocked_by": "SETUP", "direction": "LONG",
                         "trigger_level": 128.9}]
    # v3.9 acilis penceresi saate bagimlidir; bu test TETIK MANTIGINI
    # olcuyor, pencereyi degil -> seans ortasi sabitlenir (aksi halde
    # test gunun saatine gore rastgele kirilir).
    sched._minutes_since_open = lambda now_et=None: 120.0

    sched.run_fine_scan()

    assert sched.last_fine_info["trigger_hits"] == 1
    assert sched._md.hourly_requests == [["AAPL"]]     # tek sembol cekildi
    assert any("SINYAL | AAPL | LONG" in m for m in notifier.sent)
    assert len(tracker.recent_signals(5)) == 1          # golge takibe girdi

    # cooldown: hemen ikinci tetik denenmez
    sched.run_fine_scan()
    assert sched.last_fine_info["trigger_hits"] == 0


def test_trigger_not_crossed_no_reeval(tmp_path):
    sched, _, notifier, _ = _sched(tmp_path, {"AAPL": 128.0})
    sched._watchlist = [{"symbol": "AAPL", "state": "CANDIDATE",
                         "blocked_by": "SETUP", "direction": "LONG",
                         "trigger_level": 128.9}]
    sched.run_fine_scan()
    assert sched.last_fine_info["trigger_hits"] == 0
    assert sched._md.hourly_requests == []


def test_watch_collect_arms_trigger_level(tmp_path):
    """Kaba tarama SETUP'ta takilan adaya tetik seviyesi takar."""
    from app.models.decision import Bias, Decision, DecisionType
    sched, _, _, _ = _sched(tmp_path, {})
    d = Decision.base("AAPL", "1d", "1h")
    d.decision = DecisionType.NO_TRADE
    d.failed_filters = ["SETUP"]
    d.trend_bias = Bias.BULLISH
    hourly = fx.make_series(np.linspace(100, 110, 60), symbol="AAPL")
    watch: list = []
    sched._collect_watch(d, watch, hourly)
    assert watch[0]["direction"] == "LONG"
    assert watch[0]["trigger_level"] > 105   # son yapinin tepesi civari
