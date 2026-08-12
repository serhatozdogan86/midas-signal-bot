"""Konsey aksiyonlari 1/4/5: SPY kiyasi, arsiv saklama+budama, kalite metrikleri."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np

from app.config.settings import Settings
from app.scheduler import Scheduler
from app.services.database import Database
from app.services.gist_backup import GistBackup
from app.services.market_calendar import MarketCalendar
from app.services.signal_tracker import SignalTracker
from app.services.state_store import InMemoryStateStore
from tests import fixtures as fx
from tests.test_gist_backup import FakeGistClient
from tests.test_scheduler import FakeNotifier


def _tracker(tmp_path):
    return SignalTracker(Database(str(tmp_path / "c.db")), "1h")


def _sig(db, symbol, status="FILLED", closed_utc=None, created="2026-07-29T14:00:00Z",
         fill=101.0):
    db.execute(
        "INSERT INTO signals(symbol,direction,created_utc,entry_candle_ts,"
        "entry_min,entry_max,stop_loss,tp1,tp2,rr,status,outcome,closed_utc,"
        "fill_price) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (symbol, "LONG", created, 1000, 100.0, 101.0, 98.0, 106.0, 110.0,
         2.5, status, "WIN" if status == "CLOSED" else None, closed_utc,
         fill if status in ("FILLED", "CLOSED") else None))


def test_benchmark_spy_same_period(tmp_path):
    tracker = _tracker(tmp_path)
    _sig(tracker._db, "AAPL", created="2026-07-20T14:00:00Z")
    settings = Settings(TELEGRAM_ENABLED=False, STATE_BACKEND="memory")
    sched = Scheduler(settings, None, None, None, MarketCalendar(),
                      InMemoryStateStore(), FakeNotifier(), tracker)
    spy = fx.make_series(np.linspace(100, 110, 30), symbol="SPY", interval="1d")
    sched._daily_cache = {"SPY": spy}
    sched._daily_cache_date = sched._calendar.now_et().date()
    b = sched.benchmark_info()
    assert b is not None and b["since"] == "2026-07-20"
    assert b["spy_return_pct"] > 0


def test_benchmark_windows_only_signal_period(tmp_path):
    """v4.19 regresyon kaniti: sinyal ONCESI ralli benchmark'a sizamaz.

    Kurgu: SPY ilk 30 barda 100->150 kosar, son 10 bar 150'de yatay.
    Sinyal yatay bolgede dogar. Eski kod (RangeIndex yuzunden pencereyi
    kesemeyip TUM seriyi alan dal) ~+%50 raporlardi; dogrusu ~%0.
    Bu test eski kodda KIRILIR (kirilabildigi kanitli).
    """
    import numpy as np
    from datetime import datetime, timedelta, timezone

    tracker = _tracker(tmp_path)
    created = ((datetime.now(timezone.utc) - timedelta(days=8))
               .strftime("%Y-%m-%dT00:00:00Z"))
    _sig(tracker._db, "AAPL", created=created)
    settings = Settings(TELEGRAM_ENABLED=False, STATE_BACKEND="memory")
    sched = Scheduler(settings, None, None, None, MarketCalendar(),
                      InMemoryStateStore(), FakeNotifier(), tracker)
    closes = np.concatenate([np.linspace(100, 150, 30), np.full(10, 150.0)])
    spy = fx.make_series(closes, symbol="SPY", interval="1d")
    sched._daily_cache = {"SPY": spy}
    sched._daily_cache_date = sched._calendar.now_et().date()
    b = sched.benchmark_info()
    assert b is not None and b["since"] == created[:10]
    assert abs(b["spy_return_pct"]) < 2.0   # eski kod: ~+50


def test_archive_symbols_retention(tmp_path):
    tracker = _tracker(tmp_path)
    now = datetime.now(timezone.utc)
    _sig(tracker._db, "OPEN1", status="FILLED")
    _sig(tracker._db, "FRESH", status="CLOSED",
         closed_utc=(now - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    _sig(tracker._db, "STALE", status="CLOSED",
         closed_utc=(now - timedelta(days=45)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    syms = tracker.archive_symbols(retention_days=30)
    assert "OPEN1" in syms and "FRESH" in syms and "STALE" not in syms


def test_gist_prune_deletes_stale_candles(tmp_path):
    tracker = _tracker(tmp_path)
    _sig(tracker._db, "AAPL", status="FILLED")
    client = FakeGistClient()
    backup = GistBackup(client, tracker)
    backup.sync()                                  # gist olusur
    gid = backup._gist_id
    # gist'te saklama disi kalan eski bir mum dosyasi varmis gibi yap
    client.store[gid]["files"]["candles_OLD_1d.csv"] = "ts,open\n1,2"
    backup._last_sync = 0
    backup.sync()
    assert "candles_OLD_1d.csv" not in client.store[gid]["files"]   # budandi


def test_fill_quality_mfe_mae(tmp_path):
    tracker = _tracker(tmp_path)
    _sig(tracker._db, "AAPL", status="FILLED", fill=101.0)
    closes = np.array([102.0, 104.0, 100.0, 103.0])
    series = fx.make_series(closes, symbol="AAPL")
    for i, c in enumerate(series.candles):
        c.ts = 2000 + i * 3_600_000
        c.high = c.close + 0.5
        c.low = c.close - 0.5
    tracker.record_candles(series)
    fq = tracker.fill_quality()
    assert fq["n"] == 1
    # risk=3; MFE=(104.5-101)/3=+1.17R  MAE=(99.5-101)/3=-0.5R
    assert abs(fq["per"][0]["mfe_r"] - 1.17) < 0.02
    assert abs(fq["per"][0]["mae_r"] + 0.5) < 0.02


def test_eod_extras_text(tmp_path):
    tracker = _tracker(tmp_path)
    _sig(tracker._db, "AAPL", status="FILLED")
    settings = Settings(TELEGRAM_ENABLED=False, STATE_BACKEND="memory")
    sched = Scheduler(settings, None, None, None, MarketCalendar(),
                      InMemoryStateStore(), FakeNotifier(), tracker)
    spy = fx.make_series(np.linspace(100, 105, 30), symbol="SPY", interval="1d")
    sched._daily_cache = {"SPY": spy}
    sched._daily_cache_date = sched._calendar.now_et().date()
    txt = sched.build_eod_extras()
    assert "SPY ayni donem" in txt and "Setup dagilimi" in txt


def test_portfolio_cap_blocks_dispatch(tmp_path):
    """Konsey #2: eszamanli tavan doluyken SIGNAL takip/bildirim almaz."""
    from tests.test_fine_scan import FineMD
    tracker = _tracker(tmp_path)
    for i in range(10):                       # tavan dolu (10 acik)
        _sig(tracker._db, f"S{i}", status="PENDING")
    settings = Settings(TELEGRAM_ENABLED=True, STATE_BACKEND="memory",
                        MAX_OPEN_SIGNALS=10)
    notifier = FakeNotifier()
    sched = Scheduler(settings, FineMD({}), None, None, MarketCalendar(),
                      InMemoryStateStore(), notifier, tracker)
    assert sched._portfolio_cap_reason() is not None

    hourly = fx.make_series(fx.hourly_breakout_closes(),
                            volumes=fx.spike_volumes(178, spike_at=-1, mult=2.6))
    sched._daily_cache = sched._md.get_daily_bulk(["AAPL", "SPY"])
    sched._daily_cache_date = sched._calendar.now_et().date()
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
    sched._md.hourly = hourly
    sched._fine_reevaluate("AAPL")            # motor SIGNAL uretir ama...
    assert notifier.sent == []                # bildirim yok
    assert tracker.open_count() == 10         # takibe girmedi


def test_daily_cap(tmp_path):
    tracker = _tracker(tmp_path)
    settings = Settings(TELEGRAM_ENABLED=False, STATE_BACKEND="memory",
                        MAX_DAILY_SIGNALS=2)
    sched = Scheduler(settings, None, None, None, MarketCalendar(),
                      InMemoryStateStore(), FakeNotifier(), tracker)
    sched._signals_today = ["A LONG", "B LONG"]
    assert "gunluk tavan" in sched._portfolio_cap_reason()


def test_golive_status_progress(tmp_path):
    tracker = _tracker(tmp_path)
    now = datetime.now(timezone.utc)
    for i, r in enumerate([1.5, -1.0, 2.0]):
        tracker._db.execute(
            "INSERT INTO signals(symbol,direction,created_utc,entry_candle_ts,"
            "entry_min,entry_max,stop_loss,tp1,tp2,rr,status,outcome,"
            "r_multiple,closed_utc,cluster_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"G{i}", "LONG", "2026-07-20T14:00:00Z", 1, 100, 101, 98, 106,
             110, 2.5, "CLOSED", "WIN" if r > 0 else "LOSS", r,
             (now - timedelta(days=3 - i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
             f"LONG-2026-07-2{i}"))
    settings = Settings(TELEGRAM_ENABLED=False, STATE_BACKEND="memory",
                        GOLIVE_MIN_DECIDED=3, GOLIVE_MIN_EXPECTANCY_R=0.5,
                        GOLIVE_MIN_CLUSTERS=3, GOLIVE_MAX_CLUSTER_SHARE=0.5,
                        CONFIG_LOCK_UTC="2026-07-01T00:00:00Z")  # kohort filtre testte acik
    sched = Scheduler(settings, None, None, None, MarketCalendar(),
                      InMemoryStateStore(), FakeNotifier(), tracker)
    g = sched.golive_status()
    assert g["criteria"]["decided"]["now"] == 3
    # beklenti NET'tir; 2 Agu'dan itibaren maliyet cift yonlu kayma iceriyor
    assert g["criteria"]["expectancy_r"]["basis"] == "net"
    assert abs(g["criteria"]["expectancy_r"]["now"] - 0.763) < 0.01
    # v4.22: DD artik NET egriden (beklentiyle ayni muhasebe). Brut dusus
    # 1.0R; net egri her islemden maliyet dustugu icin biraz daha derin.
    dd = g["criteria"]["max_dd_r"]["now"]
    assert 1.0 < dd < 1.3
    assert g["criteria"]["clusters"]["now"] == 3        # uc ayri kume
    # v4.30: istatistik sarti eklendi. Bu 3 islemlik karisik defterde
    # (biri kayip) CI alt siniri sifirin ALTINDADIR -> kapi artik dogru
    # olarak KAPALI. v4.30 oncesi kod burada met=True derdi; yeni sartin
    # tam gorevi bu kucuk-orneklem sansini kesmek (go-live-kriteri.md #4).
    assert g["criteria"]["ci_low_r"]["now"] < 0
    assert g["criteria"]["ci_low_r"]["ok"] is False
    assert g["met"] is False
    assert "Go-live kriteri" in sched.build_eod_extras()


def test_universe_interim_seed_and_tolerant_get(tmp_path):
    """Bayat-ama-yakin (<=4 gun) yedek ara-tohum kabul edilir ve servis
    edilir; hazirlik gunluk tazeligi ayrica saglar."""
    from datetime import date, timedelta

    from app.services.universe import UniverseProvider
    settings = Settings(UNIVERSE_SOURCE="static",
                        UNIVERSE_CACHE_PATH=str(tmp_path / "u.json"))
    p = UniverseProvider(settings, market_data=None)
    # ZAMAN BAGIMSIZLIGI (3 Agu): tarihler GERCEK bugune gore kurulur.
    # Eskiden sabit 2026-07-30 kullaniliyordu; get_symbols() ise
    # _et_today() ile karsilastirma yaptigi icin test, takvim ilerledikce
    # kendiliginden kirildi (gece yarisi patlayan saatli bomba).
    today = date.today()
    yesterday = (today - timedelta(days=1)).isoformat()
    assert p.restore(["AAPL", "MSFT"], yesterday, today=today)
    assert p.get_symbols() == ["AAPL", "MSFT"]      # ara-tohum servis edildi
    assert not p.restore(["X"], (today - timedelta(days=10)).isoformat(),
                         today=today)


def test_cost_r_fixed_fee_model(tmp_path):
    """Midas sabit ucret modeli: dar stop -> buyuk nosyonel -> yuksek maliyet."""
    tracker = _tracker(tmp_path)
    tight = tracker.cost_r({"fill_price": 100.0, "stop_loss": 99.5})   # %0.5 stop
    wide = tracker.cost_r({"fill_price": 100.0, "stop_loss": 95.0})    # %5 stop
    assert tight > wide                       # dar stop daha pahali (sabit ucret!)
    # kayma artik CIFT yonlu (giris+cikis): 3$ + 2000*2*0.0005 = 5$ -> 0.05R
    assert abs(wide - (3.0 + 2000 * 2 * 0.0005) / 100) < 0.001


def test_blocked_cohort_excluded_from_score(tmp_path):
    """Tavan kohortu yasar ama karneye karismaz; hypo toplami ayri raporlanir."""
    from app.models.decision import (Bias, Confidence, Decision, DecisionType,
                                     Direction, EntryZone, SetupType, Targets)
    tracker = _tracker(tmp_path)
    d = Decision.base("CAPX", "1d", "1h")
    d.decision = DecisionType.SIGNAL
    d.direction = Direction.LONG
    d.timestamp_utc = "2026-07-30T14:00:00Z"
    d.entry_zone = EntryZone(min=100.0, max=101.0)
    d.stop_loss = 98.0
    d.targets = Targets(tp1=106.0, tp2=110.0)
    d.rr = 2.5
    d.confidence = Confidence.HIGH
    d.setup_type = SetupType.BREAKOUT_RETEST
    hourly = fx.make_series(__import__("numpy").array([100.5, 100.6]),
                            symbol="CAPX")
    for i, c in enumerate(hourly.candles):
        c.ts = 1000 + i * 3_600_000
    assert tracker.track_portfolio_blocked(d, hourly, "eszamanli tavan (10)")
    assert not tracker.track_portfolio_blocked(d, hourly, "x")   # dedupe
    assert tracker.open_count() == 0             # gercek deftere sayilmadi
    assert tracker.stats()["open_signals"] == 0
    assert tracker.recent_signals(10) == []      # arayuze karismaz
    assert "CAPX" in tracker.open_symbols()      # ama yasiyor (eval icin)
    row = tracker._db.query_one("SELECT blocked,block_reason,cluster_id,"
                                "engine_sha FROM signals")
    assert row["blocked"] == 2 and "tavan" in row["block_reason"]
    assert row["cluster_id"] == "LONG-2026-07-30"
    assert len(row["engine_sha"]) == 12
    assert tracker.blocked_summary()["total"] == 1


def test_normal_signal_stamped_with_cluster_and_sha(tmp_path):
    from tests.test_signal_tracker import _signal, _track
    tracker = _tracker(tmp_path)
    d = _signal()
    _track(tracker, d)
    row = tracker._db.query_one("SELECT cluster_id, engine_sha FROM signals")
    assert row["cluster_id"].startswith(d.direction.value + "-")
    assert row["engine_sha"] and row["engine_sha"] != "unknown"


def test_regime_hysteresis_neutral_in_band():
    """MA'ya sarkan tek kapanis bull ilan ettirmez (P1 histerezis)."""
    import pandas as pd

    from app.strategies.regime_detector import classify_index
    n = 260
    base = pd.Series([100.0 + i * 0.2 for i in range(n)])
    df = pd.DataFrame({"close": base})
    assert classify_index(df) == "bull"            # bandin acik ustunde
    df2 = df.copy()
    ma = df2["close"].rolling(200).mean().iloc[-1]
    df2.loc[n - 1, "close"] = ma * 1.001           # son kapanis bant ICINDE
    assert classify_index(df2) == "neutral"        # teyit yok -> notr


def test_heat_direction_and_cluster_caps(tmp_path):
    from datetime import datetime, timezone

    tracker = _tracker(tmp_path)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for i in range(3):                     # ayni gun ayni yon: 3 acik
        tracker._db.execute(
            "INSERT INTO signals(symbol,direction,created_utc,entry_candle_ts,"
            "entry_min,entry_max,stop_loss,tp1,tp2,rr,status,cluster_id) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"H{i}", "LONG", f"{today}T14:00:00Z", 1, 100, 101, 98, 106,
             110, 2.5, "PENDING", f"LONG-{today}"))
    settings = Settings(TELEGRAM_ENABLED=False, STATE_BACKEND="memory",
                        MAX_CLUSTER_SIGNALS=3, MAX_DIR_SIGNALS=8)
    sched = Scheduler(settings, None, None, None, MarketCalendar(),
                      InMemoryStateStore(), FakeNotifier(), tracker)
    from app.models.decision import Decision, Direction
    d = Decision.base("NEW", "1d", "1h")
    d.direction = Direction.LONG
    d.timestamp_utc = f"{today}T15:00:00Z"
    reason = sched._portfolio_cap_reason(d)
    assert reason and "kume" in reason             # 3/3 kume dolu


def test_deadman_alert_once(tmp_path):
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo

    tracker = _tracker(tmp_path)
    settings = Settings(TELEGRAM_ENABLED=True, STATE_BACKEND="memory",
                        DEADMAN_SCAN_STALENESS_MIN=25)
    notifier = FakeNotifier()
    sched = Scheduler(settings, None, None, None, MarketCalendar(),
                      InMemoryStateStore(), notifier, tracker)
    sched.last_scan_info = {"ts_utc": (datetime.now(timezone.utc)
                            - timedelta(minutes=40)).strftime("%Y-%m-%dT%H:%M:%SZ")}
    # v4.13: alarm artik ISINMA suresinde bastirilir. Bu senaryo
    # "gercekten kilitlenmis dongu"yu temsil ediyor, yani servis uzun
    # suredir ayakta olmali.
    import time as _t
    sched._started_at = _t.time() - 3600
    now = datetime(2026, 7, 30, 11, 0, tzinfo=ZoneInfo("America/New_York"))
    open_dt = now.replace(hour=9, minute=30)
    sched._deadman_check(now, open_dt, now.date())
    sched._deadman_check(now, open_dt, now.date())
    alerts = [m for m in notifier.sent if "DEAD-MAN" in m]
    assert len(alerts) == 1


def test_recent_signals_exposes_entry_evidence(tmp_path):
    """2 Agu ozelligi: setup_level/volume_note/confluence/invalidation
    contract_json'dan cozulup recent_signals() ciktisina eklenir."""
    from app.models.decision import (Decision, Direction, EntryZone,
                                     SetupType, Targets, TimeFrames)
    from tests.test_signal_tracker import _track

    tracker = _tracker(tmp_path)
    d = Decision(
        symbol="EVID", timestamp_utc="2026-08-02T14:00:00Z",
        timeframes=TimeFrames(htf="1d", mtf="1h"),
        decision="SIGNAL", direction=Direction.LONG,
        entry_zone=EntryZone(min=100.0, max=101.0), stop_loss=98.0,
        targets=Targets(tp1=106.0, tp2=110.0), rr=2.5,
        setup_type=SetupType.TREND_PULLBACK, setup_level=99.4,
        volume_note="trend_pullback @ 99.4 (hacim 1.62x ort)",
        confluence=["RS üst %20", "sektör güçlü"],
        invalidation="1h kapanış 98 altında veya 99.4 altında kabul")
    _track(tracker, d)
    rows = tracker.recent_signals(10)
    row = rows[0]
    assert row["setup_level"] == 99.4
    assert "1.62x" in row["volume_note"]
    assert row["confluence"] == ["RS üst %20", "sektör güçlü"]
    assert "98" in row["invalidation"]
    assert "contract_json" not in row      # yanit sisirilmesin


def test_recent_signals_graceful_without_evidence(tmp_path):
    """Eski sinyallerde (contract_json'da bu alanlar yoksa) sessizce atlanir."""
    from tests.test_signal_tracker import _signal, _track
    tracker = _tracker(tmp_path)
    _track(tracker, _signal())
    row = tracker.recent_signals(10)[0]
    assert "setup_level" not in row
    assert "contract_json" not in row
