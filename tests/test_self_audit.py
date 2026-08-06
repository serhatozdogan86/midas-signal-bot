"""v4.8 oz-denetim: degismezler gercekten BOZULMAYI yakaliyor mu?

Her test once SAGLIKLI durumu kurar (kontrol gecmeli), sonra o
degismezi BOZAR (kontrol dusmeli). Yalnizca 'gecti' testleri yazmak
denetimin ise yaradigini gostermez.
"""
from __future__ import annotations

import time

from app.services.database import Database
from app.services.self_audit import run_audit
from app.services.signal_tracker import SignalTracker


class _Uni:
    def __init__(self, stale=0):
        self.stale = stale

    def describe(self):
        return {"stale_days": self.stale, "filtered_count": 300}


class _Earn:
    def __init__(self, ready=True):
        self.ready = ready

    def status(self):
        return {"ready": self.ready, "symbols": 1496, "fail_streak": 0}


class _Gist:
    def __init__(self, hours=1.0):
        self.hours = hours

    def info(self):
        ts = time.gmtime(time.time() - self.hours * 3600)
        return {"last_sync_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", ts)}


def _db(tmp_path):
    d = Database(str(tmp_path / "a.db"))
    SignalTracker(d, "1h")
    return d


def _check(rep, name):
    return next(c for c in rep.checks if c.name == name)


def _add_signal(db, **kw):
    f = {"symbol": "AAPL", "direction": "LONG", "status": "PENDING",
         "blocked": 0, "engine_sha": "abc123", "created_utc": "2020-01-01T00:00:00Z"}
    f.update(kw)
    cols = ",".join(f)
    db.execute(f"INSERT INTO signals({cols}) VALUES({','.join('?' * len(f))})",
               tuple(f.values()))


def test_healthy_system_passes_all(tmp_path):
    db = _db(tmp_path)
    rep = run_audit(db=db, universe=_Uni(0), earnings=_Earn(True),
                    gist=_Gist(1), engine_sha="abc123")
    assert rep.ok, rep.telegram_text()


def test_stale_universe_is_caught(tmp_path):
    rep = run_audit(db=_db(tmp_path), universe=_Uni(5), earnings=_Earn(True),
                    gist=_Gist(1))
    c = _check(rep, "evren tazeligi")
    assert not c.ok and c.severity == "critical" and c.action


def test_missing_earnings_calendar_is_critical(tmp_path):
    rep = run_audit(db=_db(tmp_path), universe=_Uni(0), earnings=_Earn(False),
                    gist=_Gist(1))
    assert not _check(rep, "bilanco takvimi").ok


def test_signal_born_while_calendar_down_is_caught(tmp_path):
    """3 Agu vakasinin ta kendisi: takvim yokken sinyal dogmus."""
    db = _db(tmp_path)
    _add_signal(db, created_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                              time.gmtime()))
    rep = run_audit(db=db, universe=_Uni(0), earnings=_Earn(False),
                    gist=_Gist(1))
    c = _check(rep, "bilanco korumasi")
    assert not c.ok and c.severity == "critical"


def test_filled_without_fill_price_is_caught(tmp_path):
    db = _db(tmp_path)
    _add_signal(db, status="FILLED")
    tr = SignalTracker(db, "1h")
    rep = run_audit(db=db, tracker=tr, universe=_Uni(0), earnings=_Earn(True),
                    gist=_Gist(1))
    assert not _check(rep, "dolum tutarliligi").ok


def test_duplicate_open_signal_is_caught(tmp_path):
    db = _db(tmp_path)
    _add_signal(db)
    _add_signal(db)
    tr = SignalTracker(db, "1h")
    rep = run_audit(db=db, tracker=tr, universe=_Uni(0), earnings=_Earn(True),
                    gist=_Gist(1))
    assert not _check(rep, "mukerrer acik sinyal").ok


def test_engine_sha_drift_is_caught(tmp_path):
    db = _db(tmp_path)
    _add_signal(db, engine_sha="ESKI999")
    rep = run_audit(db=db, universe=_Uni(0), earnings=_Earn(True),
                    gist=_Gist(1), engine_sha="YENI111")
    c = _check(rep, "motor surumu")
    assert not c.ok and c.severity == "critical"


def test_stale_gist_backup_is_caught(tmp_path):
    rep = run_audit(db=_db(tmp_path), universe=_Uni(0), earnings=_Earn(True),
                    gist=_Gist(72))
    assert not _check(rep, "gist yedegi").ok


def test_telegram_text_lists_failures_and_actions(tmp_path):
    rep = run_audit(db=_db(tmp_path), universe=_Uni(9), earnings=_Earn(False),
                    gist=_Gist(1))
    txt = rep.telegram_text()
    assert "KRITIK" in txt and "evren tazeligi" in txt and "->" in txt


def test_audit_never_mutates_state(tmp_path):
    """Denetim SALT OKUR - defteri degistirmemeli."""
    db = _db(tmp_path)
    _add_signal(db)
    before = db.query("SELECT * FROM signals")
    run_audit(db=db, universe=_Uni(0), earnings=_Earn(True), gist=_Gist(1))
    assert db.query("SELECT * FROM signals") == before


# ------------------- v4.9: bildirim kanali kontrolu
def test_muted_alert_channel_is_critical(tmp_path):
    """4-5 Agu vakasi: TELEGRAM_ENABLED=false oldugu icin KRITIK
    uyarilar da sessizce yutuluyordu ve haftalarca fark edilmedi."""
    rep = run_audit(db=_db(tmp_path), universe=_Uni(0), earnings=_Earn(True),
                    gist=_Gist(1),
                    telegram={"configured": True, "alerts_on": False,
                              "muted": 42, "failed": 0})
    c = _check(rep, "uyari kanali")
    assert not c.ok and c.severity == "critical"
    assert "TELEGRAM_ALERTS_ENABLED" in c.action


def test_unconfigured_telegram_is_caught(tmp_path):
    rep = run_audit(db=_db(tmp_path), universe=_Uni(0), earnings=_Earn(True),
                    gist=_Gist(1),
                    telegram={"configured": False, "alerts_on": True,
                              "muted": 0, "failed": 0})
    assert not _check(rep, "uyari kanali").ok


def test_healthy_alert_channel_passes(tmp_path):
    rep = run_audit(db=_db(tmp_path), universe=_Uni(0), earnings=_Earn(True),
                    gist=_Gist(1),
                    telegram={"configured": True, "alerts_on": True,
                              "muted": 0, "failed": 0})
    assert _check(rep, "uyari kanali").ok


def test_claude_md_covers_nonnegotiables():
    """CLAUDE.md yeni oturumlarin anayasasi. Icindeki pazarliksiz
    kurallar SILINMEMELI - silinirse yeni bir oturum kilit kohortunu
    veya fail-closed disiplinini bilmeden bozabilir."""
    from pathlib import Path
    doc = Path("CLAUDE.md").read_text(encoding="utf-8")
    for kural in ("Asla uydurma veri gösterme",
                  "fail-closed",
                  "Kilit kohortuna dokunma",
                  "Ölçüm etiketleri karara karışmaz",
                  "Deploy penceresi",
                  "Yalnızca yeşilse push"):
        assert kural in doc, kural
    # es degerler dokumanla tutarli olmali
    assert "60 sonuçlanan işlem" in doc and "+0.15R" in doc
