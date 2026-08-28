"""Hipotez 7 olcusu (28 Agu ayna kapisi) - sonuc uyusmazligi raporu.

Kural (research-log hipotez 7): uyusmazlik orani >= %25 ise dolum
modeli karar toplantisina tasinir. Burada olculen sey ORAN DEGIL,
oranin nasil hesaplandigi: payda, siniflar ve yon. Kapi gunu sayilar
gorulmeden yazildi.
"""
from __future__ import annotations

from app.services.alpaca_mirror import (disagreement_report, ledger_class,
                                        mirror_class)


def _p(symbol, defter, ayna, reason=None, outcome=None, status="CLOSED"):
    return {"symbol": symbol, "status": status, "outcome": outcome or defter,
            "fill_price": 100.0, "alpaca_status": ayna,
            "closed_reason": reason}


def test_siniflar_iki_sozlugu_ortak_dile_cevirir():
    assert ledger_class("CLOSED", "NOT_FILLED", None) == "DOLMADI"
    assert ledger_class("CLOSED", "WIN", 100.0) == "KAZANC"
    assert ledger_class("CLOSED", "EXPIRED", 100.0) == "SURE"
    assert mirror_class("CANCELLED", "WINDOW") == "DOLMADI"
    assert mirror_class("CLOSED", "TP") == "KAZANC"
    assert mirror_class("CLOSED", "STOP") == "ZARAR"
    assert mirror_class("CLOSED", "TIME") == "SURE"


def test_sonuclanmamis_kayit_paydaya_girmez():
    """'Henuz bilmiyoruz' ile 'ayrildilar' ayni sey degil (2.2 refleksi):
    ayna pozisyonu hala acikken (FILLED) cift sayilmaz."""
    assert ledger_class("FILLED", None, 100.0) is None
    assert mirror_class("FILLED", None) is None
    rep = disagreement_report([
        _p("AAA", "WIN", "CLOSED", reason="TP"),
        {"symbol": "BBB", "status": "FILLED", "outcome": None,
         "fill_price": 100.0, "alpaca_status": "FILLED",
         "closed_reason": None},
    ])
    assert rep["karsilastirilan"] == 1
    assert rep["sonuclanmamis"] == 1
    assert rep["uyusmaz"] == 0


def test_dolum_ayrismasi_da_uyusmazliktir():
    """FTNT vakasi: biri girdi, digeri girmedi. Hipotez 7 tam olarak
    bundan dogdu - 'dolmadi' bir sonuc SINIFIDIR."""
    rep = disagreement_report([
        _p("FTNT", "NOT_FILLED", "CLOSED", reason="TP"),
        _p("CCC", "LOSS", "CANCELLED", reason="WINDOW"),
    ])
    assert rep["uyusmaz"] == 2
    assert rep["yon"]["yalniz_ayna_girdi"] == 1
    assert rep["yon"]["yalniz_defter_girdi"] == 1


def test_esik_yuzde_25_te_asilir():
    """Tam %25 'asildi' sayilir (>= kurali). 4'te 1 uyusmazlik."""
    rows = [_p(f"S{i}", "WIN", "CLOSED", reason="TP") for i in range(3)]
    rows.append(_p("X", "WIN", "CLOSED", reason="STOP"))
    rep = disagreement_report(rows)
    assert rep["karsilastirilan"] == 4
    assert rep["uyusmazlik_orani"] == 0.25
    assert rep["esik_asildi"] is True


def test_esigin_altinda_asilmaz():
    rows = [_p(f"S{i}", "WIN", "CLOSED", reason="TP") for i in range(9)]
    rows.append(_p("X", "WIN", "CLOSED", reason="STOP"))
    rep = disagreement_report(rows)
    assert rep["uyusmazlik_orani"] == 0.1
    assert rep["esik_asildi"] is False


def test_hic_cift_yoksa_oran_uydurulmaz():
    """Veri yoksa 0.0 degil None - 'uyusmazlik yok' ile 'olculemedi'
    ayni sey degildir (2.1)."""
    rep = disagreement_report([])
    assert rep["uyusmazlik_orani"] is None
    assert rep["esik_asildi"] is False


def test_bilinmeyen_kapanis_nedeni_gizlenmez():
    """Ayna 'CLOSED' ama neden bilinmiyorsa BELIRSIZ olur ve defterle
    uyusmaz sayilir - sessizce 'kazanc' varsayilmaz."""
    rep = disagreement_report([_p("ZZZ", "WIN", "CLOSED", reason=None)])
    assert rep["uyusmaz"] == 1
    assert rep["ornekler"][0]["ayna"] == "BELIRSIZ"
