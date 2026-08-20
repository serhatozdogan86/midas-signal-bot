"""v4.33: ayna ham-fark metrikleri + kurulus artefakti korumasi +
hafta sonu takvim muafiyeti + NOT_FILLED maliyet duzeltmesi.

Hepsi 16 Agu Durum kontrolunun bulgularindan (DE/JNJ kurulus artefakti,
takvimin her hafta sonu kirmizi yanacak olmasi, dolmayan kayda komisyon
yazilmasi). Esikler config-lock v4.32-C'de ON-KAYITLI - buradaki testler
o sozlesmenin kilididir.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.services.database import Database
from app.services.self_audit import run_audit
from app.services.signal_tracker import SignalTracker
from tests.test_alpaca_mirror_step2 import (FakeClient, _candles,
                                            _signal_row, _setup)


def _mirror_pair(db, m, symbol, ledger_fill, mirror_status,
                 mirror_fill=None, stop=98.0, direction="LONG",
                 created="2026-08-14T14:00:00Z", late=False,
                 entry_min=100.0, entry_max=101.0):
    """signals + mirror_fills cifti kur (metrics icin)."""
    db.execute(
        "INSERT INTO signals(symbol,direction,created_utc,entry_candle_ts,"
        "entry_min,entry_max,stop_loss,tp1,status,outcome,fill_price,blocked)"
        " VALUES(?,?,?,?,?,?,?,?,?,?,?,0)",
        (symbol, direction, created, 1000, entry_min, entry_max, stop, 104.0,
         "CLOSED" if ledger_fill is None else "FILLED",
         "NOT_FILLED" if ledger_fill is None else None, ledger_fill))
    sid = db.query_one("SELECT id FROM signals ORDER BY id DESC LIMIT 1")["id"]
    db.execute(
        "INSERT INTO mirror_fills(signal_id,symbol,direction,created_utc,"
        "entry_min,entry_max,stop_loss,tp1,alpaca_status,alpaca_fill_price,"
        "closed_reason) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (sid, symbol, direction, created, 100.0, 101.0, stop, 104.0,
         mirror_status, mirror_fill, "LATE_ONBOARD" if late else None))


def test_gec_katilan_sinyale_emir_gonderilmez(tmp_path):
    """DE/JNJ vakasi: dolum penceresi gecmis sinyale emir GITMEZ,
    kayit LATE_ONBOARD olur ve metrige girmez. Eski kodda emir gider,
    3 sn sonra WINDOW iptali yerdi (14 Agu sahada yasandi)."""
    db, m = _setup(tmp_path, FakeClient())
    row = _signal_row(db, "DE")
    _candles(db, "DE", 20)                    # pencere (14) coktan gecti
    assert m.sync_signals([row]) == 0
    assert m._client.orders == {}             # emir HIC gonderilmedi
    rec = db.query_one("SELECT * FROM mirror_fills WHERE symbol='DE'")
    assert rec["alpaca_status"] == "CANCELLED"
    assert rec["closed_reason"] == "LATE_ONBOARD"
    assert m.metrics()["matched"] == 0        # metrige sizmadi


def test_metrics_oran_fiyat_ve_dislama(tmp_path):
    """WFC tipi (ikisi de doldu, ayna daha iyi fiyat), TER tipi (ayna
    doldu, defter dolmadi), LATE_ONBOARD (dislanir)."""
    db, m = _setup(tmp_path, FakeClient())
    # ikisi de doldu: defter 88.63 (worst-fill = bolgenin ust ucu),
    # ayna 88.53 -> avantaj (88.63-88.53)/TASARIM riski(88.63-86.63=2.0)
    # = +0.05R (v4.42: payda tasarim riski)
    _mirror_pair(db, m, "WFC", 88.63, "FILLED", 88.53, stop=86.63,
                 entry_min=87.6, entry_max=88.63)
    # ayna girdi, defter girmedi
    _mirror_pair(db, m, "TER", None, "FILLED", 406.30, stop=395.0)
    # kurulus artefakti - hesaba KATILMAZ
    _mirror_pair(db, m, "DE", 100.5, "CANCELLED", late=True)
    mm = m.metrics()
    assert mm["matched"] == 2                 # DE dislandi
    assert mm["ledger_fill_rate"] == 0.5      # WFC dolu, TER dolmadi
    assert mm["mirror_fill_rate"] == 1.0      # ikisi de ayna tarafinda dolu
    assert mm["fill_rate_diff"] == 0.5
    assert mm["price_pairs"] == 1
    assert abs(mm["avg_price_adv_r"] - 0.05) < 0.001
    # oran farki 0.5 >= 0.10 -> kademe 1 (izleme notu); kademe 2 DEGIL
    # cunku 20 cift yok - sabir kurali kodda da yasiyor
    assert mm["tier"] == 1


def test_gap_dolumu_paydayi_patlatamaz(tmp_path):
    """CIEN vakasi (20 Agu): defter gap'te BOLGENIN ALTINDAN, stop'a 2.2
    puan mesafeden doldu; eski payda (dolum riski) cokunce tek cift
    -10.5R 'sapma' uretip 13 ciftin ortalamasini ele gecirdi. v4.42:
    payda TASARIM riski - ayni cift artik sinirli (-0.91R) olculur.
    Eski kodda bu test kirmizi yanar."""
    db, m = _setup(tmp_path, FakeClient())
    _mirror_pair(db, m, "CIEN", 421.585, "CLOSED", 445.11,
                 stop=419.355, entry_min=432.4604, entry_max=445.27)
    mm = m.metrics()
    assert mm["price_pairs"] == 1
    # tasarim riski 25.915 -> (421.585-445.11)/25.915 = -0.908
    assert -1.0 < mm["avg_price_adv_r"] < -0.8
    # eski payda (dolum riski 2.23) -10.5 uretirdi - o dunya kapandi
    assert mm["avg_price_adv_r"] > -2.0


def test_tier2_ancak_orneklem_ve_sure_dolunca(tmp_path):
    """Karar tetigi (kademe 2) kucuk orneklemde ATESLENEMEZ; 20 cift +
    14 gun dolunca ve fark buyukse ateslenir (on-kayit sozlesmesi)."""
    db, m = _setup(tmp_path, FakeClient())
    for i in range(20):
        _mirror_pair(db, m, f"S{i}", None, "FILLED", 100.0,
                     created="2026-07-01T14:00:00Z")   # >14 gun once
    mm = m.metrics()
    assert mm["matched"] == 20 and mm["fill_rate_diff"] == 1.0
    assert mm["tier"] == 2


def test_audit_takvim_hafta_sonu_muafiyeti(tmp_path):
    """Hafta sonu bayat takvim kirmizi YAKMAZ (yuklu + hatasiz sartiyla);
    hafta ici ayni durum kirmizi YAKAR. Duvar saatinden bagimsiz:
    'now' parametresiyle."""
    class _E:
        def status(self):
            return {"ready": False, "symbols": 1490, "fail_streak": 0}

    db = Database(str(tmp_path / "a.db"))
    SignalTracker(db, "1h")
    sat = datetime(2026, 8, 16, 12, tzinfo=timezone.utc)     # Pazar
    mon = datetime(2026, 8, 17, 12, tzinfo=timezone.utc)     # Pazartesi
    rep_we = run_audit(db=db, earnings=_E(), now=sat)
    cal_we = [c for c in rep_we.checks if c.name == "bilanco takvimi"][0]
    assert cal_we.ok is True and "muafiyet" in cal_we.detail
    rep_wd = run_audit(db=db, earnings=_E(), now=mon)
    cal_wd = [c for c in rep_wd.checks if c.name == "bilanco takvimi"][0]
    assert cal_wd.ok is False
    # muafiyet CEKME HATASI varsa gecerli degil (ariza gizlenmez)
    class _E2:
        def status(self):
            return {"ready": False, "symbols": 1490, "fail_streak": 3}
    rep_f = run_audit(db=db, earnings=_E2(), now=sat)
    assert [c for c in rep_f.checks
            if c.name == "bilanco takvimi"][0].ok is False


def test_not_filled_kayda_maliyet_yazilmaz(tmp_path):
    """16 Agu bulgusu: dolmayan emirde komisyon/kayma DOGMAZ. Eski kod
    NOT_FILLED'e de cost_r/-0.08R gosteriyordu (rapor katmani)."""
    db = Database(str(tmp_path / "c.db"))
    tr = SignalTracker(db, "1h")
    db.execute(
        "INSERT INTO signals(symbol,direction,created_utc,entry_candle_ts,"
        "entry_min,entry_max,stop_loss,tp1,rr,status,outcome,r_multiple,"
        "blocked) VALUES('DAL','LONG','2026-07-29T13:30:00Z',1000,"
        "86.01,87.015,84.0,90.0,2.5,'CLOSED','NOT_FILLED',0.0,0)")
    db.execute(
        "INSERT INTO signals(symbol,direction,created_utc,entry_candle_ts,"
        "entry_min,entry_max,stop_loss,tp1,rr,status,outcome,r_multiple,"
        "fill_price,blocked) VALUES('WFC','LONG','2026-08-13T14:00:00Z',"
        "1000,87.6,88.63,86.63,92.6,2.5,'CLOSED','WIN',2.0,88.63,0)")
    rows = {r["symbol"]: r for r in tr.recent_signals(10)}
    assert "cost_r" not in rows["DAL"] and "r_net" not in rows["DAL"]
    assert rows["WFC"]["cost_r"] > 0          # gerceklesen isleme maliyet var
