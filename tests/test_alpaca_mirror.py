"""Ayna katmani (v4.19 adim 1) - izolasyon sozlesmesi kilitleri.

Uc guvence test edilir (sozlesme: app/services/alpaca_mirror.py docstring):
1. IMPORT KILIDI: karar modulleri (strategies/*, signal_tracker) aynayi
   import edemez - AST duzeyinde taranir (2.4 deseninin aynisi).
2. SEMA AYRIKLIGI: ayna kendi tablosuna yazar; signals tablosunda
   mirror/alpaca alani yoktur; self_audit 13. degismezi bunu canlida izler
   ve KIRILABILDIGI bu dosyada gosterilir (sutun eklenince kizarir).
3. VARSAYILAN KAPALI: ALPACA_MIRROR_ENABLED False; kapaliyken tek satir
   bile yazilmaz.
"""
from __future__ import annotations

import ast
from pathlib import Path

from app.config.settings import Settings
from app.services.alpaca_mirror import AlpacaMirror
from app.services.database import Database
from app.services.self_audit import run_audit

ROOT = Path(__file__).resolve().parents[1]

# Karar modulleri: sinyal uretimi ve defter muhasebesi. scheduler bilincli
# olarak DISARIDA - orkestrasyon katmani aynayi cagirmaya yetkilidir.
DECISION_MODULES = sorted((ROOT / "app" / "strategies").glob("*.py")) + [
    ROOT / "app" / "services" / "signal_tracker.py",
]


def _imported_modules(path: Path) -> list[str]:
    names: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
            names += [f"{node.module}.{a.name}" for a in node.names]
    return names


def test_karar_modulleri_aynayi_import_etmez():
    for path in DECISION_MODULES:
        bad = [m for m in _imported_modules(path) if "alpaca_mirror" in m]
        assert not bad, f"{path.name} ayna modulunu import ediyor: {bad}"


def test_defter_semasinda_ayna_alani_yok(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    cols = [r["name"] for r in db.query("PRAGMA table_info(signals)")]
    leak = [c for c in cols if "mirror" in c.lower() or "alpaca" in c.lower()]
    assert not leak


def test_ayna_kendi_tablosuna_yazar_ve_dedup(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    m = AlpacaMirror(db, enabled=True)
    row = {"id": 7, "symbol": "AAPL", "direction": "LONG",
           "entry_min": 100.0, "entry_max": 101.0,
           "stop_loss": 98.0, "tp1": 104.0}
    before = db.query_one("SELECT COUNT(*) AS n FROM signals")["n"]
    assert m.record_intent(row) is True
    assert db.query_one("SELECT COUNT(*) AS n FROM mirror_fills")["n"] == 1
    # signals tablosuna tek satir bile yazilmadi (tek yonlu akis)
    assert db.query_one("SELECT COUNT(*) AS n FROM signals")["n"] == before
    # ayni sinyal ikinci kez kayit ACMAZ (dedup, cift sayim dersi)
    assert m.record_intent(row) is False
    assert m.diag()["intents"] == 1
    assert m.diag()["label"] == "AYNA - karara girmez"


def test_varsayilan_kapali_ve_kapaliyken_yazmaz(tmp_path):
    # Settings ORNEGI kurulmaz (ortam degiskenine duyarli olur); alan
    # varsayilani dogrudan modelden okunur - test duvar/ortamdan bagimsiz.
    assert Settings.model_fields["ALPACA_MIRROR_ENABLED"].default is False
    db = Database(str(tmp_path / "t.db"))
    m = AlpacaMirror(db, enabled=False)
    assert m.record_intent({"id": 1, "symbol": "AAPL",
                            "direction": "LONG"}) is False
    assert db.query_one("SELECT COUNT(*) AS n FROM mirror_fills")["n"] == 0


def test_denetim_degismez13_ayna_izolasyonu_kirilabilir(tmp_path):
    """13. degismezin hem yesili hem KIRMIZISI gosterilir (4.1/3 kurali:
    yalnizca 'gecti' senaryosu kontrolun calistigini kanitlamaz)."""
    db = Database(str(tmp_path / "t.db"))
    rep = run_audit(db)
    c = next(x for x in rep.checks if x.name == "ayna izolasyonu")
    assert c.ok, c.detail
    # izolasyonu bilerek DEL: signals'a ayna alani ekle -> degismez kizarmali
    db.execute("ALTER TABLE signals ADD COLUMN mirror_r REAL")
    rep2 = run_audit(db)
    c2 = next(x for x in rep2.checks if x.name == "ayna izolasyonu")
    assert not c2.ok
    assert "mirror_r" in c2.detail
    assert c2.severity == "critical"
