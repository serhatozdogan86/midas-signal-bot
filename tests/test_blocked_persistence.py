"""v4.21: blocked kohortlari restart'i ATLATMALI.

VAKA (7 Agu bulgusu): gist yedegi 0_signals.json'i recent_signals()'tan
uretir ve o sorgu blocked=0 filtrelidir (karne icin DOGRU) - ama restore
da ayni dosyadan yukler. Sonuc: v3.9'dan beri her restart tum blocked
kohortlarini (2=tavan, 3=kill-switch, 4=acilis penceresi, 5=hacim/pullback
hipotezi) sessizce siliyordu; korumalarin "kacirdigimiz R" olcumu ve
hipotez kohortu HIC birikemedi. Tuzak tablosundaki "turetilmis veriyi
bellekte tutmak" dersinin gist bicimi.

DUZELTME: blocked satirlar AYRI dosyada (0_signals_blocked.json)
yedeklenir, restore geri yukler; dosya yoksa (eski yedekler) sessizce
atlanir (geriye uyum). Bu testler eski kodda KIRMIZI yanar - once test
yazildi, kirildigi goruldu, sonra duzeltildi (4.1/3 kurali).
"""
from __future__ import annotations

import json

from app.services.database import Database
from app.services.gist_backup import GistBackup
from app.services.signal_tracker import SignalTracker


class _Client:
    """Yedek yazan sahte istemci (test_gist_persistence._Client esi)."""

    def create_gist(self, *a, **k):
        return "gist123"

    def update_gist(self, *a, **k):
        return True

    def find_gist(self, *a, **k):
        return "gist123"

    def gist_url(self, gid):
        return f"https://gist.github.com/{gid}"


class _FetchClient(_Client):
    """Restore icin: fetch_gist sabit dosya seti dondurur."""

    def __init__(self, files):
        self.files = files

    def fetch_gist(self, gid):
        return self.files


def _seed(db) -> None:
    """1 gercek + 2 blocked satir (biri acik kill-switch, biri sonuclanmis
    hipotez - hypo_r tasir). Kolonlar track_blocked ile birebir."""
    db.execute(
        "INSERT INTO signals(symbol,direction,created_utc,status,blocked,"
        "entry_min,entry_max,stop_loss,tp1,rr,cluster_id,engine_sha) "
        "VALUES('AAPL','LONG','2026-08-07T14:00:00Z','PENDING',0,"
        "100,101,98,104,2.5,'LONG-2026-08-07','abc123')")
    db.execute(
        "INSERT INTO signals(symbol,direction,created_utc,status,blocked,"
        "block_reason,entry_min,entry_max,stop_loss,tp1,rr,cluster_id,"
        "engine_sha) VALUES('MSFT','LONG','2026-08-07T14:05:00Z','PENDING',3,"
        "'kill-switch: SPY -0.9%',200,202,195,210,2.1,"
        "'LONG-2026-08-07','abc123')")
    db.execute(
        "INSERT INTO signals(symbol,direction,created_utc,status,outcome,"
        "blocked,block_reason,entry_min,entry_max,stop_loss,tp1,rr,"
        "r_multiple,closed_utc,cluster_id,engine_sha) "
        "VALUES('NVDA','SHORT','2026-08-05T15:00:00Z','CLOSED','WIN',5,"
        "'hipotez/hacim: pullback 1.10x < 1.30x esigi (yalniz gozlem)',"
        "120,121,125,114,2.2,1.7,'2026-08-06T20:00:00Z',"
        "'SHORT-2026-08-05','abc123')")


def test_blocked_kohortlar_yedege_girer(tmp_path):
    db = Database(str(tmp_path / "a.db"))
    tr = SignalTracker(db, "1h")
    _seed(db)
    files = GistBackup(_Client(), tr, pinned_gist_id="gist123").build_files()
    # eski kodda bu dosya HIC uretilmiyordu
    assert "0_signals_blocked.json" in files
    blk = json.loads(files["0_signals_blocked.json"])
    assert {r["symbol"] for r in blk} == {"MSFT", "NVDA"}
    assert all(r["blocked"] for r in blk)
    by_sym = {r["symbol"]: r for r in blk}
    assert by_sym["NVDA"]["r_multiple"] == 1.7          # hypo_r kaynagi
    assert "hipotez" in by_sym["NVDA"]["block_reason"]
    # gercek-sinyal dosyasina blocked SIZMAMALI (karne ayrimi korunur)
    assert {r["symbol"] for r in json.loads(files["0_signals.json"])} == {"AAPL"}


def test_restore_donus_turu_blocked_koruur(tmp_path):
    """Tam donus turu: yedek al -> taze DB'ye restore -> kohortlar yerinde."""
    db1 = Database(str(tmp_path / "a.db"))
    tr1 = SignalTracker(db1, "1h")
    _seed(db1)
    files = GistBackup(_Client(), tr1, pinned_gist_id="gist123").build_files()

    db2 = Database(str(tmp_path / "b.db"))          # restart: bos disk
    tr2 = SignalTracker(db2, "1h")
    bk2 = GistBackup(_FetchClient(files), tr2, pinned_gist_id="gist123")
    assert bk2.restore_if_empty() is True
    bs = tr2.blocked_summary()
    assert bs["total"] == 2 and bs["open"] == 1
    assert bs["by_class"]["3"]["n"] == 1
    assert bs["by_class"]["5"] == {"n": 1, "hypo_r": 1.7}
    row = db2.query_one("SELECT * FROM signals WHERE symbol='NVDA'")
    assert row["blocked"] == 5 and row["outcome"] == "WIN"
    assert row["cluster_id"] == "SHORT-2026-08-05"   # kume kimligi de tasinir
    # gercek satir da geldi ve blocked=0 kaldi
    real = db2.query_one("SELECT * FROM signals WHERE symbol='AAPL'")
    assert (real["blocked"] or 0) == 0
    # idempotent: ikinci import cift kayit acmaz
    tr2.import_signals_blocked(json.loads(files["0_signals_blocked.json"]))
    assert tr2.blocked_summary()["total"] == 2


def test_eski_yedek_blocked_dosyasiz_geriye_uyumlu(tmp_path):
    """v4.21 oncesi yedeklerde 0_signals_blocked.json yok - restore
    kirilmadan calismali (dosya yok = kohort yok, hata degil)."""
    db1 = Database(str(tmp_path / "a.db"))
    tr1 = SignalTracker(db1, "1h")
    _seed(db1)
    old_files = {"0_signals.json": json.dumps(tr1.recent_signals(500))}
    db2 = Database(str(tmp_path / "b.db"))
    tr2 = SignalTracker(db2, "1h")
    bk2 = GistBackup(_FetchClient(old_files), tr2, pinned_gist_id="gist123")
    assert bk2.restore_if_empty() is True
    assert tr2.blocked_summary()["total"] == 0
    assert db2.query_one("SELECT COUNT(*) n FROM signals")["n"] == 1


def test_karar_arsivi_restore_edilir(tmp_path):
    """v4.28 (10 Agu vakasi): kararlar yedekten donmeyince her deploy
    arsivi sifirliyor ve ilk sync BOS arsivi gist'e yazip GECMISI DE
    siliyordu (21:08'de 468 KB -> [] oldu). Donus turu + idempotentlik."""
    db1 = Database(str(tmp_path / "a.db"))
    tr1 = SignalTracker(db1, "1h")
    for i in range(3):
        db1.execute(
            "INSERT INTO decisions(ts_utc,symbol,decision,direction,"
            "market_regime,trend_bias,setup_type,reject_reason) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (f"2026-08-10T1{i}:00:00Z", f"S{i}", "SIGNAL" if i == 0
             else "NO_TRADE", "LONG", "BULL", "BULLISH",
             "breakout_retest", None if i == 0 else "RR dusuk"))
    files = GistBackup(_Client(), tr1, pinned_gist_id="gist123").build_files()
    assert "0_decisions.json" in files

    db2 = Database(str(tmp_path / "b.db"))
    tr2 = SignalTracker(db2, "1h")
    bk2 = GistBackup(_FetchClient(files), tr2, pinned_gist_id="gist123")
    assert bk2.restore_if_empty() is True
    rows = db2.query("SELECT * FROM decisions ORDER BY ts_utc")
    assert len(rows) == 3
    assert rows[0]["decision"] == "SIGNAL" and rows[0]["symbol"] == "S0"
    assert rows[2]["reject_reason"] == "RR dusuk"
    # idempotent: ikinci import cift kayit acmaz
    assert tr2.import_decisions(json.loads(files["0_decisions.json"])) == 0
