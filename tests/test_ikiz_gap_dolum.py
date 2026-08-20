"""IKIZ TARAMASI (2026-08-21): gap dolumunun R paydasi uzerindeki etkisi.

Bulgu kaynagi: kilit-2 kohortunda JNJ +7.91R. Dolum bolgenin ALTINDA
(256.00 vs bolge 258.02-259.03) olustugu icin R paydasi 4.00 yerine
1.475'e dustu; bolge ici dolumda ayni cikis +2.29R olurdu.

Bu dosya kurali DEGISTIRMEZ - davranisi SABITLER (karakterizasyon).
Olctugu sey: `_evaluate_signal` gap dalinin (acilis bolgenin otesindeyse
dolum acilistan) R uzerindeki ASIMETRIK etkisi.

  - kazanan islemde R sisiyor (payda kuculur, pay buyur)
  - kaybeden islemde R DEGISMEZ (-1.0'a capalidir)

Asimetri onemli: kural beklentiyi yalnizca YUKARI itebilir. Ikiz olcum
docs/ikiz-depo-notu.md "G1" maddesinde.
"""
from __future__ import annotations

from app.services.database import Database
from app.services.signal_tracker import SignalTracker

# Ortak kurgu: bolge 100.0-101.0, stop 98.0, tp1 104.0
# tasarim riski (bolge ortasi 100.5 -> stop 98) = 2.50
# bolge kenari dolumu (101.0)              -> risk 3.00
# gap dolumu (acilis 99.0)                 -> risk 1.00
ENTRY_MIN, ENTRY_MAX, STOP, TP1 = 100.0, 101.0, 98.0, 104.0


def _tracker(tmp_path, name="t.db"):
    db = Database(str(tmp_path / name))
    return db, SignalTracker(db, "1h")


def _seed(db, symbol="AAPL"):
    db.execute(
        "INSERT INTO signals(symbol,direction,created_utc,entry_candle_ts,"
        "entry_min,entry_max,stop_loss,tp1,tp2,rr,time_stop_date,status,"
        "cluster_id,engine_sha) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (symbol, "LONG", "2026-08-20T14:00:00Z", 1000,
         ENTRY_MIN, ENTRY_MAX, STOP, TP1, 108.0, 2.5, "2026-08-27",
         "PENDING", "LONG-2026-08-20", "test"))


def _candles(db, symbol, rows):
    db.executemany(
        "INSERT OR IGNORE INTO candles(symbol,interval,ts,open,high,low,"
        "close,volume) VALUES(?,?,?,?,?,?,?,?)",
        [(symbol, "1h", ts, o, h, lo, c, 1000.0) for ts, o, h, lo, c in rows])


def _run(tmp_path, name, fill_bar, sonuc_bar):
    db, tr = _tracker(tmp_path, name)
    _seed(db)
    _candles(db, "AAPL", [fill_bar, sonuc_bar])
    tr.evaluate_open("AAPL")
    return db.query_one("SELECT * FROM signals")


# --- gap bari: acilis 99.0 bolgenin (100.0) ALTINDA -> dolum acilistan
_GAP_FILL = (2000, 99.0, 100.4, 98.5, 100.2)
# --- normal bar: acilis 100.6 bolge ICINDE, low 100.0 bolgeyi katediyor
_EDGE_FILL = (2000, 100.6, 101.2, 100.0, 100.8)
# --- sonuc barlari
_TP_BAR = (5_602_000, 102.0, 104.5, 101.5, 104.2)     # tp1 104 gorulur
_STOP_BAR = (5_602_000, 99.5, 99.8, 97.5, 97.8)       # stop 98 gorulur


def test_gap_acilisinda_dolum_acilistan_yazilir(tmp_path):
    """Kural: LONG'da acilis entry_min'in altindaysa dolum ACILISTAN.
    (signal_tracker._evaluate_signal, 'gap ile bolgenin OTESINDE acilis')"""
    row = _run(tmp_path, "a.db", _GAP_FILL, _TP_BAR)
    assert row["fill_price"] == 99.0, (
        "gap dali tetiklenmedi - dolum acilistan yazilmali")
    # payda: 99.0 - 98.0 = 1.00; tasarim riski 2.50 idi -> 2.5 kat kucuk
    assert abs((row["fill_price"] - STOP) - 1.0) < 1e-9


def test_bolge_ici_dolumda_payda_kenardan(tmp_path):
    """Karsilastirma kolu: gap yoksa dolum bolgenin KOTU ucundan (101.0),
    payda 3.00. Ayni cikis, uc kat buyuk payda."""
    row = _run(tmp_path, "b.db", _EDGE_FILL, _TP_BAR)
    assert row["fill_price"] == ENTRY_MAX
    assert abs((row["fill_price"] - STOP) - 3.0) < 1e-9


def test_gap_dolumu_kazanan_islemde_R_sisirir(tmp_path):
    """ASIL BULGU: ayni sinyal, ayni cikis, tek fark dolum bari.
    Gap kolunda R, bolge-ici koluna gore kat kat buyuk cikar."""
    gap = _run(tmp_path, "c.db", _GAP_FILL, _TP_BAR)
    edge = _run(tmp_path, "d.db", _EDGE_FILL, _TP_BAR)
    assert gap["outcome"] == edge["outcome"] == "WIN"
    assert gap["exit_price"] == edge["exit_price"], "cikis ayni olmali"
    # (104-99)/1.00 = 5.00R  vs  (104-101)/3.00 = 1.00R
    assert abs(gap["r_multiple"] - 5.0) < 0.01
    assert abs(edge["r_multiple"] - 1.0) < 0.01
    assert gap["r_multiple"] >= 4 * edge["r_multiple"], (
        f"sisme kayboldu: gap {gap['r_multiple']} vs kenar "
        f"{edge['r_multiple']}")


def test_gap_dolumu_kaybeden_islemde_R_DEGISTIRMEZ(tmp_path):
    """ASIMETRI: zarar tanimi geregi stop'a kadardir, yani her iki kolda
    da tam -1R. Kural beklentiyi YALNIZCA yukari itebilir - bu yuzden
    gap yogun kohortlarda beklenti yukari yanlidir."""
    gap = _run(tmp_path, "e.db", _GAP_FILL, _STOP_BAR)
    edge = _run(tmp_path, "f.db", _EDGE_FILL, _STOP_BAR)
    assert gap["outcome"] == edge["outcome"] == "LOSS"
    assert abs(gap["r_multiple"] - (-1.0)) < 0.01
    assert abs(edge["r_multiple"] - (-1.0)) < 0.01
    assert abs(gap["r_multiple"] - edge["r_multiple"]) < 0.01, (
        "zarar kolunda fark cikti - asimetri iddiasi gecersiz")
