"""Scheduler testleri: dispatch/cooldown + seans saatine bagli gorev tetikleme."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.config.settings import Settings
from app.models.decision import (
    Decision, DecisionType, Direction, EntryZone, Targets,
)
from app.scheduler import Scheduler
from app.services.market_calendar import MarketCalendar
from app.services.state_store import InMemoryStateStore

ET = ZoneInfo("America/New_York")


class FakeNotifier:
    def __init__(self):
        self.sent: list[str] = []

    def send(self, text: str) -> bool:
        self.sent.append(text)
        return True


def _signal(symbol="AAPL") -> Decision:
    d = Decision.base(symbol, "1d", "1h")
    d.decision = DecisionType.SIGNAL
    d.direction = Direction.LONG
    d.entry_zone = EntryZone(min=98.5, max=99.2)
    d.targets = Targets(tp1=101.0, tp2=103.0)
    return d


def _scheduler(**settings_kw):
    settings_kw.setdefault("TELEGRAM_ENABLED", True)
    settings_kw.setdefault("STATE_BACKEND", "memory")
    settings = Settings(**settings_kw)
    notifier = FakeNotifier()
    sched = Scheduler(settings, market_data=None, universe=None, earnings=None,
                      calendar=MarketCalendar(), store=InMemoryStateStore(),
                      notifier=notifier)
    return sched, notifier


def test_dispatch_signal_and_cooldown():
    sched, notifier = _scheduler()
    sched._dispatch(_signal())
    sched._dispatch(_signal())          # cooldown -> gonderilmez
    assert len(notifier.sent) == 1
    assert "SINYAL | AAPL | LONG" in notifier.sent[0]


def test_dispatch_no_trade_suppressed_by_default():
    sched, notifier = _scheduler(SEND_NO_TRADE=False)
    d = Decision.base("MSFT", "1d", "1h")   # NO_TRADE
    sched._dispatch(d)
    assert notifier.sent == []


def test_telegram_disabled_mutes_all():
    sched, notifier = _scheduler(TELEGRAM_ENABLED=False)
    sched._dispatch(_signal())
    assert notifier.sent == []


# ------------------------------------------------------- seans saati tetikleri
def _instrument(sched, monkeypatch):
    calls = []
    def fake_prep(today):
        calls.append("prep")
        sched._prep_date = today
    def fake_coarse(send_telegram=True):
        calls.append("coarse")
        return []
    def fake_eod(today):
        calls.append("eod")
        sched._eod_date = today
    monkeypatch.setattr(sched, "run_prep", fake_prep)
    monkeypatch.setattr(sched, "run_coarse_scan", fake_coarse)
    monkeypatch.setattr(sched, "run_eod", fake_eod)
    return calls


def test_tick_weekend_sleeps(monkeypatch):
    sched, _ = _scheduler()
    calls = _instrument(sched, monkeypatch)
    sched.tick(datetime(2026, 7, 25, 12, 0, tzinfo=ET))  # cumartesi
    assert calls == []


def test_tick_prep_then_scan_then_eod(monkeypatch):
    sched, _ = _scheduler()
    calls = _instrument(sched, monkeypatch)
    day = (2026, 7, 28)  # sali - normal seans

    sched.tick(datetime(*day, 7, 0, tzinfo=ET))    # cok erken -> hicbir sey
    assert calls == []
    sched.tick(datetime(*day, 8, 50, tzinfo=ET))   # 08:45 sonrasi -> prep
    assert calls == ["prep"]
    sched.tick(datetime(*day, 8, 55, tzinfo=ET))   # prep tekrar etmez
    assert calls == ["prep"]
    sched._last_coarse = 0.0
    sched.tick(datetime(*day, 10, 0, tzinfo=ET))   # seans ici -> kaba tarama
    assert calls == ["prep", "coarse"]
    sched.tick(datetime(*day, 16, 20, tzinfo=ET))  # kapanis+15dk -> gun sonu
    assert calls == ["prep", "coarse", "eod"]
    sched.tick(datetime(*day, 16, 30, tzinfo=ET))  # eod tekrar etmez
    assert calls == ["prep", "coarse", "eod"]


# --------------------------------------- uctan uca kaba tarama entegrasyonu
def test_coarse_scan_with_tracker_and_gist(tmp_path):
    """Tarama -> SIGNAL -> Telegram + shadow kayit + gist sync zinciri."""
    from datetime import date

    from app.models.decision import EarningsInfo
    from app.services.database import Database
    from app.services.gist_backup import GistBackup
    from app.services.signal_tracker import SignalTracker
    from tests import fixtures as fx
    from tests.test_gist_backup import FakeGistClient

    daily_up = fx.make_series(fx.daily_uptrend_closes(), interval="1d",
                              spread=0.02)
    hourly_pb = fx.make_series(fx.hourly_pullback_long_closes(),
                               volumes=fx.spike_volumes(110))

    class FakeMD:
        def __init__(self):
            self.daily_calls = 0
            self.hourly_requests: list[list[str]] = []

        def get_daily_bulk(self, symbols, period=None):
            self.daily_calls += 1
            out = {}
            for s in symbols:
                closes = (fx.daily_flat_closes() if s == "FLAT"
                          else fx.daily_uptrend_closes())
                out[s] = fx.make_series(closes, symbol=s, interval="1d",
                                        spread=0.02)
            return out

        def get_hourly_bulk(self, symbols):
            self.hourly_requests.append(list(symbols))
            return {s: hourly_pb for s in symbols}

    class FakeUniverse:
        def get_symbols(self):
            return ["AAPL", "FLAT"]

        def describe(self):
            return {"filtered_count": 1}

    class FakeEarnings:
        def refresh(self, today, force=False):
            pass

        def info(self, symbol, today):
            return EarningsInfo(next_date="2026-08-20", days_to=8)

    tracker = SignalTracker(Database(str(tmp_path / "t.db")), "1h")
    gist_client = FakeGistClient()
    gist = GistBackup(gist_client, tracker, sync_interval_sec=0)
    settings_kw = dict(TELEGRAM_ENABLED=True, STATE_BACKEND="memory")
    settings = Settings(**settings_kw)
    notifier = FakeNotifier()
    sched = Scheduler(settings, FakeMD(), FakeUniverse(), FakeEarnings(),
                      MarketCalendar(), InMemoryStateStore(), notifier,
                      tracker, gist)

    md = sched._md
    results = sched.run_coarse_scan(send_telegram=True)

    assert len(results) == 2
    by_sym = {d.symbol: d for d in results}
    assert by_sym["AAPL"].decision.value == "SIGNAL"
    assert by_sym["AAPL"].time_stop_date is not None  # takvimle zenginlesti
    assert by_sym["FLAT"].decision.value == "NO_TRADE"
    assert by_sym["FLAT"].failed_filters == ["TREND"]
    # 2. gecis: 1h verisi YALNIZ gunluk filtreleri gecen aday icin istendi
    assert md.hourly_requests == [["AAPL"]]
    # gunluk cache: ayni gun ikinci taramada yeniden indirilmez
    daily_calls_first = md.daily_calls
    sched.run_coarse_scan(send_telegram=False)
    assert md.daily_calls == daily_calls_first
    assert any("SINYAL | AAPL | LONG" in m for m in notifier.sent)
    assert len(tracker.recent_signals(5)) == 1        # shadow kayda alindi
    assert tracker.recent_signals(5)[0]["time_stop_date"] is not None
    assert len(tracker.recent_decisions(9)) == 4      # 2 sembol x 2 tarama
    assert tracker.candles_count() > 0                # 1h + 1d arsivlendi
    assert len(gist_client.store) == 1                # gist olustu ve sync oldu
