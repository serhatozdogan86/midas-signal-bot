"""Ayna uyusmazlik anatomisi (karar toplantisi B adimi, 1 Eyl 2026).

Olculen sey SONUC degil, olcunun kendisi: nufuz orani dogru mu
hesaplaniyor, hangi vakalar hukme giriyor, on-kayitli yorum kurali
esiklerde ne diyor. Sayilar sahadan gelmeden yazildi.
"""
from __future__ import annotations

from app.services.mirror_anatomy import (anatomy_rows, anatomy_summary,
                                         penetration)


def _pair(symbol, defter_outcome, ayna_status, reason=None, lowest=None,
          highest=None, direction="LONG", emin=100.0, emax=102.0):
    return {"symbol": symbol, "direction": direction, "status": "CLOSED",
            "outcome": defter_outcome, "fill_price": None,
            "alpaca_status": ayna_status, "closed_reason": reason,
            "entry_min": emin, "entry_max": emax, "lowest": lowest,
            "highest": highest, "alpaca_fill_price": 101.0, "bar_sayisi": 14}


def test_nufuz_orani_bolgeye_gore_olculur():
    # LONG bolge 100-102 (genislik 2). En dusuk 102 -> yalniz ust uca
    # degdi = 0.0; 101 -> yarisi = 0.5; 100 -> TAM katetti = 1.0
    assert penetration("LONG", 100.0, 102.0, 102.0, None) == 0.0
    assert penetration("LONG", 100.0, 102.0, 101.0, None) == 0.5
    assert penetration("LONG", 100.0, 102.0, 100.0, None) == 1.0
    assert penetration("LONG", 100.0, 102.0, 99.0, None) == 1.5   # otesine


def test_short_ayna_taraf_ters_uctan_olculur():
    assert penetration("SHORT", 100.0, 102.0, None, 100.0) == 0.0
    assert penetration("SHORT", 100.0, 102.0, None, 102.0) == 1.0


def test_mum_yoksa_sifir_degil_none():
    """'Mum yok' ile 'hic yaklasmadi' ayni sey degil (2.1)."""
    assert penetration("LONG", 100.0, 102.0, None, None) is None
    assert penetration("LONG", None, None, 100.0, None) is None
    assert penetration("LONG", 101.0, 101.0, 100.0, None) is None  # genislik 0


def test_yalniz_uyusmayan_ciftler_listelenir():
    rows = anatomy_rows([
        _pair("AAA", "WIN", "CLOSED", reason="TP", lowest=100.0),   # uyusuyor
        _pair("BBB", "NOT_FILLED", "CLOSED", reason="TP", lowest=101.0),
    ])
    assert [r["symbol"] for r in rows] == ["BBB"]
    assert rows[0]["nufuz"] == 0.5


def test_hukum_model_katiligi_lehine():
    """Fiyat bolgeyi neredeyse katetmis (0.95, 0.90) -> (a)."""
    rows = anatomy_rows([
        _pair("A", "NOT_FILLED", "CLOSED", reason="TP", lowest=100.1),
        _pair("B", "NOT_FILLED", "CLOSED", reason="TP", lowest=100.2),
    ])
    ozet = anatomy_summary(rows)
    assert ozet["kacirilan_vaka"] == 2
    assert ozet["medyan_nufuz"] >= 0.85
    assert "MODEL KATILIGI" in ozet["hukum"]


def test_hukum_ayna_gevsekligi_lehine():
    """Fiyat bolgeye ancak degmis (0.1) -> (b), defter DEGISMEZ."""
    rows = anatomy_rows([
        _pair("A", "NOT_FILLED", "CLOSED", reason="TP", lowest=101.8),
        _pair("B", "NOT_FILLED", "CLOSED", reason="TP", lowest=101.9),
    ])
    ozet = anatomy_summary(rows)
    assert ozet["medyan_nufuz"] <= 0.50
    assert "AYNA GEVSEKLIGI" in ozet["hukum"]


def test_arada_kalirsa_hukum_verilmez():
    rows = anatomy_rows([
        _pair("A", "NOT_FILLED", "CLOSED", reason="TP", lowest=100.6),  # 0.7
    ])
    assert "ARADA" in anatomy_summary(rows)["hukum"]


def test_cikis_ayrismasi_hukme_karismaz():
    """GD/SHW tipi (ikisi de girdi, sonuc ayristi) 'kacirilan' degildir;
    ayri sayilir - yoksa 'biz mi kacirdik' sorusunun paydasi kirlenir."""
    rows = anatomy_rows([
        _pair("GD", "EXPIRED", "CLOSED", reason="STOP", lowest=100.0),
        _pair("A", "NOT_FILLED", "CLOSED", reason="TP", lowest=100.1),
    ])
    ozet = anatomy_summary(rows)
    assert ozet["kacirilan_vaka"] == 1
    assert ozet["cikis_ayrismasi"] == 1


def test_olculebilir_vaka_yoksa_hukum_yok():
    rows = anatomy_rows([_pair("GD", "EXPIRED", "CLOSED", reason="STOP",
                               lowest=100.0)])
    assert anatomy_summary(rows)["hukum"].startswith("HUKUM YOK")
