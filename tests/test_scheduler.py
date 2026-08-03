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
        def prefetch(self, symbols, today):
            return None

        def refresh(self, today, force=False):
            pass

        def info(self, symbol, today, strict=True):
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


def test_run_prep_produces_market_note_and_warms_cache(tmp_path):
    """Hazirlik: evren + gunluk cache isitma + piyasa notu + Telegram ozeti."""
    from app.models.decision import EarningsInfo
    from app.services.commentary import CommentaryService
    from app.services.database import Database
    from app.services.signal_tracker import SignalTracker
    from tests import fixtures as fx

    hourly_pb = fx.make_series(fx.hourly_pullback_long_closes(),
                               volumes=fx.spike_volumes(110))

    class FakeMD:
        def __init__(self):
            self.daily_calls = 0

        def get_daily_bulk(self, symbols, period=None):
            self.daily_calls += 1
            return {s: fx.make_series(fx.daily_uptrend_closes(), symbol=s,
                                      interval="1d", spread=0.02)
                    for s in symbols}

        def get_hourly_bulk(self, symbols):
            return {s: hourly_pb for s in symbols}

    class FakeUniverse:
        def refresh(self, force=False):
            return ["AAPL"]

        def get_symbols(self):
            return ["AAPL"]

        def describe(self):
            return {"filtered_count": 1}

    class FakeEarnings:
        def prefetch(self, symbols, today):
            return None

        def refresh(self, today, force=False):
            pass

        def info(self, symbol, today, strict=True):
            return EarningsInfo(next_date="2026-08-20", days_to=8)

    db = Database(str(tmp_path / "p.db"))
    tracker = SignalTracker(db, "1h")
    commentary = CommentaryService(db, tracker)
    settings = Settings(TELEGRAM_ENABLED=True, STATE_BACKEND="memory")
    notifier = FakeNotifier()
    sched = Scheduler(settings, FakeMD(), FakeUniverse(), FakeEarnings(),
                      MarketCalendar(), InMemoryStateStore(), notifier,
                      tracker, None, commentary)

    today = sched._calendar.now_et().date()
    sched.run_prep(today)

    assert sched.last_market_note                     # piyasa notu uretildi
    assert "Gunluk piyasa notu" in sched.last_market_note
    prep_msgs = [m for m in notifier.sent if "Hazirlik tamam" in m]
    assert prep_msgs and "Gunluk piyasa notu" in prep_msgs[0]
    daily_calls_after_prep = sched._md.daily_calls
    assert daily_calls_after_prep >= 1

    # ayni gun kaba tarama: gunluk cache'ten okur, yeniden indirmez
    sched.run_coarse_scan(send_telegram=False)
    assert sched._md.daily_calls == daily_calls_after_prep


def test_orphan_signals_still_evaluated(tmp_path):
    """IONQ vakasi portu: evrenden dusen sembolun acik sinyali yasamali."""
    from app.services.database import Database
    from app.services.signal_tracker import SignalTracker
    from tests import fixtures as fx

    db = Database(str(tmp_path / "o.db"))
    tracker = SignalTracker(db, "1h")
    # evrende OLMAYAN sembol icin acik sinyal
    db.execute(
        "INSERT INTO signals(symbol,direction,created_utc,entry_candle_ts,"
        "entry_min,entry_max,stop_loss,tp1,tp2,rr,status,fill_price) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        ("IONQ", "LONG", "2026-07-28T14:00:00Z", 0, 100.0, 101.0,
         98.0, 106.0, 110.0, 2.5, "FILLED", 101.0))

    hourly_win = fx.make_series(
        __import__("numpy").array([102.0, 103.0, 107.0, 107.0]), symbol="IONQ")
    for i, c in enumerate(hourly_win.candles):
        c.ts = 1000 + i * 3_600_000
        c.high = c.close + 0.3
        c.low = c.close - 0.3

    class OrphanMD:
        def get_daily_bulk(self, symbols, period=None):
            return {}

        def get_hourly_bulk(self, symbols):
            assert "IONQ" in symbols          # orphan icin veri istendi
            return {"IONQ": hourly_win}

    settings = Settings(TELEGRAM_ENABLED=False, STATE_BACKEND="memory")
    sched = Scheduler(settings, OrphanMD(), None, None, MarketCalendar(),
                      InMemoryStateStore(), FakeNotifier(), tracker)
    sched._evaluate_orphans(scanned={"AAPL"})   # IONQ taranmadi

    sig = tracker.recent_signals(1)[0]
    assert sig["symbol"] == "IONQ"
    assert sig["outcome"] == "WIN"              # TP1 107 ile kesildi -> kapandi


def test_heartbeat_fires_even_off_session(monkeypatch):
    """Nabiz seans/tatil durumundan bagimsiz atar (uzaktan izleme kanali)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    sched, _ = _scheduler()
    beats = []

    class FakeGist:
        def heartbeat(self, payload):
            beats.append(payload)
            return True

        def maybe_sync(self):
            pass
    sched._gist = FakeGist()
    sched.tick(datetime(2026, 7, 25, 12, 0, tzinfo=ZoneInfo("America/New_York")))  # cumartesi
    assert len(beats) == 1
    hb = beats[0]
    assert "last_scan" in hb and "recent_warnings" in hb and "log_counts" in hb
    sched.tick(datetime(2026, 7, 25, 12, 1, tzinfo=ZoneInfo("America/New_York")))
    assert len(beats) == 1     # aralik dolmadan tekrar atmaz


def test_gap_watch_runs_before_prep_in_window(monkeypatch):
    """Restart 16:00-16:30 penceresine denk gelirse gap nobeti UZUN
    hazirligi BEKLEMEZ (30 Tem karari: 8 pozisyonun sabah sinavi korunur)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    sched, _ = _scheduler()
    order = []
    monkeypatch.setattr(sched, "run_prep", lambda d: order.append("prep"))
    monkeypatch.setattr(sched, "run_gap_watch", lambda d: order.append("gap"))
    monkeypatch.setattr(sched, "run_coarse_scan",
                        lambda **k: order.append("scan"))
    sched.tick(datetime(2026, 7, 30, 9, 10,
                        tzinfo=ZoneInfo("America/New_York")))
    assert order[0] == "gap" and "prep" in order
