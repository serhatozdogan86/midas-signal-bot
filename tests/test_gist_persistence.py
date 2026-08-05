"""v4.10: yedek zaman damgasi restart'i ATLATMALI.

Vaka: /backup/info her restart'tan sonra last_sync_utc=None
donduruyordu - yedek aliniyordu ama "ne zaman alindi" sorusu cevapsizdi.
Oz-denetim bunu hakli olarak korluk sayip bildirdi.
"""
from __future__ import annotations

import time

from app.services.database import Database
from app.services.gist_backup import GistBackup
from app.services.signal_tracker import SignalTracker


class _Client:
    def __init__(self, ok=True):
        self.ok = ok
        self.calls = 0

    def create_gist(self, *a, **k):
        self.calls += 1
        return "gist123" if self.ok else None

    def update_gist(self, *a, **k):
        self.calls += 1
        return self.ok

    def gist_url(self, gid):
        return f"https://gist.github.com/{gid}"

    def find_gist(self, *a, **k):
        return "gist123"


def _backup(db, ok=True):
    tr = SignalTracker(db, "1h")
    return GistBackup(_Client(ok), tr, pinned_gist_id="gist123")


def test_timestamp_survives_restart(tmp_path):
    db = Database(str(tmp_path / "g.db"))
    b1 = _backup(db)
    assert b1.info()["last_sync_utc"] is None      # hic yedek yok
    assert b1.sync() is True
    stamp = b1.info()["last_sync_utc"]
    assert stamp

    # RESTART taklidi: yeni nesne, AYNI veritabani
    b2 = _backup(db)
    assert b2.info()["last_sync_utc"] == stamp     # damga hayatta
    assert b2.info()["age_hours"] is not None


def test_failed_sync_does_not_stamp(tmp_path):
    db = Database(str(tmp_path / "g.db"))
    b = _backup(db, ok=False)
    assert b.sync() is False
    assert b.info()["last_sync_utc"] is None       # basarisizsa damga YOK


def test_age_hours_reflects_stored_stamp(tmp_path):
    db = Database(str(tmp_path / "g.db"))
    old = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 7200))
    db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)",
               ("gist_last_sync_utc", old))
    b = _backup(db)
    age = b.info()["age_hours"]
    assert 1.9 < age < 2.1                         # ~2 saat


def test_audit_sees_persisted_backup_age(tmp_path):
    """Oz-denetim artik restart sonrasi da yedegi dogrulayabilmeli."""
    from app.services.self_audit import run_audit
    db = Database(str(tmp_path / "g.db"))
    b = _backup(db)
    b.sync()
    b2 = _backup(db)                               # restart
    rep = run_audit(db=db, gist=b2)
    chk = next(c for c in rep.checks if c.name == "gist yedegi")
    assert chk.ok, chk.detail


def test_backup_runs_outside_session_too():
    """v4.11: maybe_sync yalniz kaba tarama sonunda cagriliyordu;
    seans kapaliyken (gece/hafta sonu) saatlerce yedek alinmiyordu.
    Render'in dosya sistemi kalici olmadigi icin restart defteri SON
    YEDEGE dondurur - bu bosluk veri kaybi demekti."""
    from pathlib import Path
    src = Path("app/scheduler.py").read_text()
    tick = src[src.index("    def tick(self"):src.index("    def run_prep(")]
    assert "self._gist.maybe_sync()" in tick, "tick'te saatlik yedek yok"
    # gun sonu kosulsuz arsiv hala yerinde olmali
    eod = src[src.index("    def run_eod(self"):]
    assert "self._gist.sync()" in eod
