"""Arastirma verisi butunluk raporu (acik kuyruk md. 9 - ikizden tasindi).

bybit'in indiricisi satir/tekrar/bosluk sayiyordu, midas'ta karsiligi
yoktu: "veri geldi" ile "veri TAM geldi" ayrimini yapamiyorduk. Sessiz
eksik veri bu depoda daha once gerceklesmis bir hata sinifi (Finnhub
takvimi ~1500 satirda sessizce kirpiyordu, v4.40).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.data import integrity


def _raw(gun=5, semboller=("AAA", "BBB"), nan_sayisi=0):
    idx = pd.bdate_range("2026-01-05", periods=gun)
    kolonlar = pd.MultiIndex.from_product([["Close", "Open"], list(semboller)])
    d = pd.DataFrame(1.0, index=idx, columns=kolonlar)
    if nan_sayisi:
        d.loc[idx[:nan_sayisi], ("Close", semboller[0])] = np.nan
    return d


def test_temiz_veride_bayrak_yok():
    r = integrity(_raw())
    assert r["gun"] == 5 and r["sembol"] == 2
    assert r["tekrar_eden_gun"] == 0
    assert r["eksik_gunu_olan_sembol"] == 0
    assert r["en_cok_eksik"] == []


def test_eksik_gunler_sayilir_ve_siralanir():
    r = integrity(_raw(gun=10, nan_sayisi=3))
    assert r["eksik_gunu_olan_sembol"] == 1
    assert r["en_cok_eksik"][0] == {"sembol": "AAA", "eksik_gun": 3}


def test_tekrar_eden_gun_yakalanir():
    """Ayni gunun iki kez gelmesi sessiz bir veri hatasidir - sayilir."""
    d = _raw(gun=4)
    ikili = pd.concat([d, d.iloc[[0]]])
    assert integrity(ikili)["tekrar_eden_gun"] == 1


def test_tarih_araligi_raporlanir():
    r = integrity(_raw(gun=3))
    assert r["ilk_gun"] == "2026-01-05"
    assert r["son_gun"] == "2026-01-07"


def test_yalniz_istenen_semboller_sayilir():
    """Indirilen tabloda fazladan sembol olabilir; rapor evrene bakar."""
    r = integrity(_raw(semboller=("AAA", "BBB", "CCC")), syms=["AAA", "BBB"])
    assert r["sembol"] == 2


def test_bos_tablo_cokmez():
    r = integrity(pd.DataFrame())
    assert r["gun"] == 0 and r["sembol"] == 0 and r["ilk_gun"] is None


def test_eksik_oran_esigi_baglayiciligi_belirler():
    """21 Eyl: hiz sinirindan 114/1628 sembol dustu (%7) ve o veriyle
    F7 dort sarti da GECTI. Esik bir PASS'i engelledigi icin lehe
    secilmis olamaz - kayit acik olsun diye test de boyle yazildi."""
    d = _raw(gun=3)
    temiz = integrity(d, istenen=100, eksik=["X", "Y"])          # %2
    assert temiz["eksik_orani"] == 0.02 and temiz["baglayici"] is True
    kirpik = integrity(d, istenen=100, eksik=["X"] * 7)          # %7
    assert kirpik["eksik_orani"] == 0.07 and kirpik["baglayici"] is False


def test_eksik_sayimi_gun_bosluklariyla_karismaz():
    """'Sembol hic gelmedi' ile 'sembolun bazi gunleri bos' AYRI
    sayilir. (Ilk yazimda ayni degisken adi kullanildigi icin ikisi
    birbirini eziyordu - 21 Eyl'de yakalandi.)"""
    d = _raw(gun=10, nan_sayisi=3)
    r = integrity(d, istenen=50, eksik=["YOK1", "YOK2"])
    assert r["eksik_sembol"] == 2              # hic gelmeyen
    assert r["eksik_gunu_olan_sembol"] == 1    # gunu eksik olan
