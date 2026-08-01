"""Aksiyon Paneli (canli durum), seans fazi ve takvim seridi testleri."""
from __future__ import annotations

from datetime import datetime, date
from zoneinfo import ZoneInfo

from app.config.settings import Settings
from app.scheduler import Scheduler
from app.services.database import Database
from app.services.market_calendar import MarketCalendar
from app.services.signal_tracker import SignalTracker
from app.services.state_store import InMemoryStateStore

ET = ZoneInfo("America/New_York")


class QuoteMD:
    def __init__(self, quotes):
        self.quotes = quotes
        self.calls = 0

    def get_quote(self, symbol):
        self.calls += 1
        return self.quotes.get(symbol)


def _sched(tmp_path, quotes, earnings=None):
    db = Database(str(tmp_path / "l.db"))
    tracker = SignalTracker(db, "1h")
    settings = Settings(TELEGRAM_ENABLED=False, STATE_BACKEND="memory")
    sched = Scheduler(settings, QuoteMD(quotes), None, earnings,
                      MarketCalendar(), InMemoryStateStore(), None, tracker)
    return sched, tracker, db


def _insert(db, symbol="AAPL", direction="LONG", status="FILLED",
            fill=101.0, stop=98.0, tp1=106.0, time_stop="2026-07-30"):
    db.execute(
        "INSERT INTO signals(symbol,direction,created_utc,entry_candle_ts,"
        "entry_min,entry_max,stop_loss,tp1,tp2,rr,time_stop_date,status,"
        "fill_price) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (symbol, direction, "2026-07-28T14:00:00Z", 1000, 100.0, 101.0,
         stop, tp1, 110.0, 2.5, time_stop, status,
         fill if status == "FILLED" else None))


def test_live_actions(tmp_path):
    sched, _, db = _sched(tmp_path, {"AAPL": 96.0, "MSFT": 100.5, "NVDA": 105.9})
    _insert(db, "AAPL")                                  # stop ihlali
    _insert(db, "MSFT", status="PENDING")                # giris bolgesinde
    _insert(db, "NVDA", fill=101.0)                      # tp1'e cok yakin
    rows = {r["symbol"]: r for r in sched.get_live_status()}
    assert "STOP IHLALI" in rows["AAPL"]["action"]
    assert rows["AAPL"]["r_now"] < -1
    assert "GIRIS BOLGESINDE" in rows["MSFT"]["action"]
    assert "TP1'e cok yakin" in rows["NVDA"]["action"]


def test_live_quote_cache(tmp_path):
    sched, _, db = _sched(tmp_path, {"AAPL": 102.0})
    _insert(db, "AAPL")
    sched.get_live_status()
    sched.get_live_status()
    assert sched._md.calls == 1        # 60 sn onbellek -> tek cagri


def test_session_info_phases(tmp_path):
    sched, _, _ = _sched(tmp_path, {})
    pre = sched.session_info(datetime(2026, 7, 28, 8, 0, tzinfo=ET))
    assert pre["phase"] == "PRE" and pre["next_event"] == "acilis"
    open_ = sched.session_info(datetime(2026, 7, 28, 12, 0, tzinfo=ET))
    assert open_["phase"] == "ACIK" and open_["next_event"] == "kapanis"
    closed = sched.session_info(datetime(2026, 7, 25, 12, 0, tzinfo=ET))  # cmt
    assert closed["phase"] == "KAPALI" and closed["next_event"] == "acilis"


def test_calendar_strip(tmp_path):
    """Tarihler dinamik: bugunden itibaren 2. ve 3. islem gunu secilir
    (sabit tarih, gun gecince patlayan saatli bombaydi - 1 Agu CI dersi)."""
    cal = MarketCalendar()
    today = cal.now_et().date()
    ts_day = cal.add_trading_days(today, 2).isoformat()
    er_day = cal.add_trading_days(today, 1).isoformat()

    class FakeEarnings:
        def info(self, symbol, today):
            from app.models.decision import EarningsInfo
            if symbol == "AAPL":
                return EarningsInfo(next_date=er_day, days_to=1)
            return EarningsInfo()

    sched, _, db = _sched(tmp_path, {}, earnings=FakeEarnings())
    _insert(db, "AAPL", time_stop=ts_day)
    strip = sched.build_calendar_strip(days=6)
    by_date = {d["date"]: d for d in strip if not d.get("holiday")}
    assert "AAPL" in by_date[ts_day]["time_stops"]
    assert "AAPL" in by_date[er_day]["earnings"]
