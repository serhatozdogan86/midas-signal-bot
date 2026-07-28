"""StateStore testleri - in-memory ve SQLite implementasyonlari ayni sozlesme."""
from __future__ import annotations

import pytest

from app.services.database import Database
from app.services.sqlite_state_store import SQLiteStateStore
from app.services.state_store import InMemoryStateStore


@pytest.fixture(params=["memory", "sqlite"])
def store(request, tmp_path):
    if request.param == "memory":
        return InMemoryStateStore()
    return SQLiteStateStore(Database(str(tmp_path / "test.db")))


def test_cooldown_roundtrip(store):
    assert not store.cooldown_active("AAPL", "LONG", 3600, now=1000.0)
    store.mark_signal_sent("AAPL", "LONG", now=1000.0)
    assert store.cooldown_active("AAPL", "LONG", 3600, now=2000.0)
    assert not store.cooldown_active("AAPL", "LONG", 3600, now=5000.0)
    assert not store.cooldown_active("AAPL", "SHORT", 3600, now=2000.0)


def test_results_and_meta(store):
    store.save_result("AAPL", {"decision": "SIGNAL"})
    store.save_result("AAPL", {"decision": "NO_TRADE"})  # upsert
    assert store.get_results()["AAPL"]["decision"] == "NO_TRADE"
    store.record_scan("2026-07-28T14:00:00Z")
    meta = store.get_meta()
    assert meta["last_scan_utc"] == "2026-07-28T14:00:00Z"
    assert meta["scan_count"] == 1
