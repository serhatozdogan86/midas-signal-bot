"""GistBackup testleri - sahte GistClient ile (ag erisimi yok)."""
from __future__ import annotations

import json

import numpy as np

from app.models.decision import (
    Decision, DecisionType, Direction, EntryZone, Targets, TimeFrames,
)
from app.services.database import Database
from app.services.gist_backup import MARKER, GistBackup, _parse_candles_csv
from app.services.signal_tracker import SignalTracker
from tests import fixtures as fx


class FakeGistClient:
    """create/update/find/fetch sozlesmesini bellekte taklit eder."""

    def __init__(self, existing: dict | None = None):
        self.store: dict[str, dict[str, str]] = existing or {}
        self.updates = 0

    def find_gist(self, marker):
        for gid, meta in self.store.items():
            if meta["description"] == marker:
                return gid
        return None

    def create_gist(self, marker, files):
        gid = f"gist{len(self.store) + 1}"
        self.store[gid] = {"description": marker, "files": dict(files)}
        return gid

    def update_gist(self, gist_id, files):
        if gist_id not in self.store:
            return False
        self.updates += 1
        for name, content in files.items():
            if content is None:
                self.store[gist_id]["files"].pop(name, None)
            else:
                self.store[gist_id]["files"][name] = content
        return True

    def fetch_gist(self, gist_id):
        meta = self.store.get(gist_id)
        return dict(meta["files"]) if meta else None

    def gist_url(self, gist_id):
        return f"https://gist.github.com/{gist_id}"


def _tracker_with_signal(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    tracker = SignalTracker(db, "1h")
    d = Decision(
        symbol="AAPL", timestamp_utc="2026-07-27T00:00:00Z",
        timeframes=TimeFrames(htf="1d", mtf="1h"),
        decision=DecisionType.SIGNAL, direction=Direction.LONG,
        entry_zone=EntryZone(min=100.0, max=101.0), stop_loss=98.0,
        targets=Targets(tp1=106.0, tp2=110.0), rr=2.5)
    mtf = fx.make_series(np.full(70, 102.0), symbol="AAPL")
    mtf.candles[-1].ts = 1_000_000
    tracker.maybe_track(d, mtf)
    tracker.record_candles(fx.make_series(np.full(30, 101.0), symbol="AAPL"))
    return tracker


def test_first_sync_creates_gist(tmp_path):
    client = FakeGistClient()
    backup = GistBackup(client, _tracker_with_signal(tmp_path),
                        meta_provider=lambda: {"universe": {"count": 3}})
    assert backup.sync() is True
    gid = client.find_gist(MARKER)
    files = client.fetch_gist(gid)
    assert "0_performance.json" in files and "0_signals.json" in files
    assert "candles_AAPL_1h.csv" in files          # candle_mode=signals
    assert json.loads(files["0_meta.json"])["universe"]["count"] == 3
    assert len(json.loads(files["0_signals.json"])) == 1


def test_second_sync_updates_same_gist(tmp_path):
    client = FakeGistClient()
    backup = GistBackup(client, _tracker_with_signal(tmp_path))
    backup.sync()
    backup.sync()
    assert len(client.store) == 1 and client.updates == 1


def test_maybe_sync_respects_interval(tmp_path):
    client = FakeGistClient()
    backup = GistBackup(client, _tracker_with_signal(tmp_path),
                        sync_interval_sec=3600)
    backup.maybe_sync()   # ilk cagri sync eder
    backup.maybe_sync()   # aralik dolmadi -> atlanir
    assert len(client.store) == 1 and client.updates == 0


def test_restore_if_empty_roundtrip(tmp_path):
    # 1) dolu tracker'dan gist'e yaz
    client = FakeGistClient()
    GistBackup(client, _tracker_with_signal(tmp_path / "a")).sync()
    # 2) BOS tracker (redeploy senaryosu) ayni gist'ten geri yuklesin
    empty = SignalTracker(Database(str(tmp_path / "b" / "t.db")), "1h")
    backup2 = GistBackup(client, empty)
    assert backup2.restore_if_empty() is True
    assert empty.candles_count() > 0
    assert len(empty.recent_signals(10)) == 1
    assert empty.recent_signals(10)[0]["symbol"] == "AAPL"


def test_restore_skips_when_db_has_data(tmp_path):
    client = FakeGistClient()
    tracker = _tracker_with_signal(tmp_path)
    backup = GistBackup(client, tracker)
    assert backup.restore_if_empty() is False      # veri zaten var


def test_parse_candles_csv_tolerates_garbage():
    text = "ts,open,high,low,close,volume\n1,2,3,4,5,6\nbozuk,satir\n7,8,9,10,11,12\n"
    rows = _parse_candles_csv(text)
    assert len(rows) == 2 and rows[0][0] == 1


def test_fetch_meta_and_universe_seed(tmp_path):
    from datetime import date

    from app.config.settings import Settings
    from app.services.universe import UniverseProvider

    client = FakeGistClient()
    backup = GistBackup(client, _tracker_with_signal(tmp_path),
                        meta_provider=lambda: {"universe": {
                            "symbols": ["AAPL", "MSFT"],
                            "filtered_date": date.today().isoformat()}})
    backup.sync()

    meta = GistBackup(client, _tracker_with_signal(tmp_path / "b")).fetch_meta()
    uni_meta = meta["universe"]
    settings = Settings(UNIVERSE_SOURCE="static",
                        UNIVERSE_CACHE_PATH=str(tmp_path / "c.json"))
    provider = UniverseProvider(settings, market_data=None)
    from datetime import date as _d
    assert provider.restore(uni_meta["symbols"], uni_meta["filtered_date"],
                            today=_d.today())
    assert provider.get_symbols() == ["AAPL", "MSFT"]      # grind atlandi
    assert not provider.restore(["X"], "2020-01-01")       # bayat yedek reddi
