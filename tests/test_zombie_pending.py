"""v4.32: DAL/UAL zombi PENDING vakasi (13 Agu 2026).

VAKA: gunluk filtrelerden dusen acik-sinyalli sembollerin 1h mumu hic
cekilmiyordu; fill_window mum-listesi INDEKSI oldugu icin mum gelmeyince
NOT_FILLED asla yazilmadi - iki kayit time_stop'tan 9 gun sonra bile
10'luk tavandan slot yedi ve 13/13 audit sessiz kaldi.

Kirilabilirlik: uc test de v4.32 oncesi kodda kirmizi yanar
(close_expired_pending yok / zaman capasi yok / audit degismezi yok).
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.services.database import Database
from app.services.self_audit import run_audit
from app.services.signal_tracker import SignalTracker


def _tracker(tmp_path):
    return SignalTracker(Database(str(tmp_path / "z.db")), "1h")


def _pending(db, symbol, time_stop, entry_ts=1785331800000):
    db.execute(
        "INSERT INTO signals(symbol,direction,created_utc,entry_candle_ts,"
        "entry_min,entry_max,stop_loss,tp1,tp2,rr,status,time_stop_date) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (symbol, "LONG", "2026-07-29T13:30:00Z", entry_ts,
         86.01, 87.015, 84.0, 90.0, 92.0, 2.5, "PENDING", time_stop))


def test_mumsuz_supurme_suresi_gecmisi_kapatir(tmp_path):
    """DAL/UAL senaryosu: mum HIC yok, time_stop 9 gun gecmis ->
    supurme fiyat gerektirmeden NOT_FILLED yazar; taze olan kalir."""
    tr = _tracker(tmp_path)
    _pending(tr._db, "DAL", "2026-08-04")
    _pending(tr._db, "TAZE", "2026-08-14")
    n = tr.close_expired_pending(today="2026-08-13")
    assert n == 1
    dal = tr._db.query_one("SELECT * FROM signals WHERE symbol='DAL'")
    assert dal["status"] == "CLOSED" and dal["outcome"] == "NOT_FILLED"
    taze = tr._db.query_one("SELECT * FROM signals WHERE symbol='TAZE'")
    assert taze["status"] == "PENDING"        # suresi gecmemis, dokunulmaz
    # idempotent
    assert tr.close_expired_pending(today="2026-08-13") == 0


def test_zaman_capasi_gec_gelen_mumla_sahte_dolumu_keser(tmp_path):
    """Mum akisi kesilip HAFTALAR sonra toptan gelirse: bolgeye
    time_stop'tan SONRA degen bar dolum TETIKLEYEMEZ (eski kodda
    indeks-tabanli pencere kayar, bar 0-13 sanilirdi -> sahte dolum).
    time_stop oncesi barlar ise GERCEK sonucu yazmaya devam eder."""
    tr = _tracker(tmp_path)
    _pending(tr._db, "DAL", "2026-08-04")
    # mumlar 12 Agu'da basliyor (giristen 2 hafta sonra) ve bolgeye giriyor
    base = int(datetime(2026, 8, 12, 14, tzinfo=timezone.utc).timestamp() * 1000)
    for i in range(4):
        ts = base + i * 3600_000
        tr._db.execute(
            "INSERT INTO candles(symbol,interval,ts,open,high,low,close,volume) "
            "VALUES('DAL','1h',?,?,?,?,?,1000)",
            (ts, 86.5, 87.0, 85.9, 86.2))     # low 85.9 <= entry_min 86.01
    tr.evaluate_open("DAL")
    row = tr._db.query_one("SELECT * FROM signals WHERE symbol='DAL'")
    assert row["status"] == "CLOSED"
    assert row["outcome"] == "NOT_FILLED"      # dolum DEGIL - pencere gecmis
    assert row["fill_price"] is None


def test_zaman_capasi_penceredeki_gercek_dolumu_korur(tmp_path):
    """Simetri kaniti: ayni mumlar time_stop'tan ONCE gelirse dolum
    GERCEKTIR ve yazilir - capa yalniz gec olani keser, erkeni bozmaz."""
    tr = _tracker(tmp_path)
    _pending(tr._db, "UAL", "2026-08-04",
             entry_ts=int(datetime(2026, 7, 29, 13, 30,
                                   tzinfo=timezone.utc).timestamp() * 1000))
    base = int(datetime(2026, 7, 30, 14, tzinfo=timezone.utc).timestamp() * 1000)
    for i in range(3):
        tr._db.execute(
            "INSERT INTO candles(symbol,interval,ts,open,high,low,close,volume) "
            "VALUES('UAL','1h',?,?,?,?,?,1000)",
            (base + i * 3600_000, 86.5, 87.0, 85.9, 86.2))
    tr.evaluate_open("UAL")
    row = tr._db.query_one("SELECT * FROM signals WHERE symbol='UAL'")
    assert row["status"] == "FILLED"
    assert row["fill_price"] == 87.015         # worst-fill kurali ayni


def test_audit_zombi_degismezi(tmp_path):
    """14. degismez: suresi gecmis PENDING varken audit YESIL KALAMAZ
    (13 Agu'da 13/13 temiz gorunmustu - bu test o sessizligi kapatir)."""
    tr = _tracker(tmp_path)
    _pending(tr._db, "DAL", "2026-08-04")
    rep = run_audit(db=tr._db, tracker=tr)
    zmb = [c for c in rep.checks if c.name == "zombi PENDING"]
    assert zmb and zmb[0].ok is False
    # supurme sonrasi ayni degismez yesile doner
    tr.close_expired_pending(today="2026-08-13")
    rep2 = run_audit(db=tr._db, tracker=tr)
    zmb2 = [c for c in rep2.checks if c.name == "zombi PENDING"]
    assert zmb2 and zmb2[0].ok is True


def test_audit_mum_tazeligi_degismezi(tmp_path):
    """15. degismez: acik sinyalin sembolunde 1h arsivi bayat/yoksa
    uyar (DAL/UAL'de arsiv 16 gun eskiydi, kimse gormedi)."""
    tr = _tracker(tmp_path)
    _pending(tr._db, "DAL", "2026-08-20")      # acik ve taze - ama mumu YOK
    rep = run_audit(db=tr._db, tracker=tr)
    fr = [c for c in rep.checks if c.name == "acik sinyal mum tazeligi"]
    assert fr and fr[0].ok is False and "DAL" in fr[0].detail
    # taze mum gelince yesil
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    tr._db.execute(
        "INSERT INTO candles(symbol,interval,ts,open,high,low,close,volume) "
        "VALUES('DAL','1h',?,90,91,89,90,1000)", (now_ms,))
    rep2 = run_audit(db=tr._db, tracker=tr)
    fr2 = [c for c in rep2.checks if c.name == "acik sinyal mum tazeligi"]
    assert fr2 and fr2[0].ok is True
