"""Portfoy katmani ve secim kurali (Faz 4 / F7) - olcunun testleri.

Test edilen sey F7'nin CEVABI degil (veri gerekir), aletin sozlesmesi:
tavanlar dogru mu isliyor, secim kurali gercekten siralama yapiyor mu,
elenen islem kayboluyor mu, ve on-kayitli hukum kurali esiklerde ne
diyor. Sayilar gorulmeden yazildi (8 Eyl 2026).
"""
from __future__ import annotations

import pandas as pd

from research.portfolio import apply_portfolio, verdict_f7


def _t(gun: str, sym: str, r: float, gun_sayisi: int = 3) -> dict:
    g = pd.Timestamp(gun)
    return {"entry_date": g, "exit_date": g + pd.Timedelta(days=gun_sayisi),
            "symbol": sym, "r_net": r, "bars_held": gun_sayisi}


def test_gunluk_tavan_uygulanir():
    """Ayni gun 8 aday, tavan 6 -> 6 secilir, 2 elenir."""
    t = pd.DataFrame([_t("2026-01-05", f"S{i}", 1.0) for i in range(8)])
    out = apply_portfolio(t, None)
    assert out["secildi"].sum() == 6
    assert (~out["secildi"]).sum() == 2


def test_elenen_islem_silinmez_isaretlenir():
    """Kacan kazanci da olcebilmek icin elenen kayit tabloda KALIR."""
    t = pd.DataFrame([_t("2026-01-05", f"S{i}", 1.0) for i in range(8)])
    out = apply_portfolio(t, None)
    assert len(out) == 8


def test_eszamanli_tavan_acik_pozisyonlari_sayar():
    """Gun 1'de 6 islem acilir (10 gun tutar), gun 2'de 6 aday daha
    gelir ama eszamanli tavan 10 -> yalniz 4 yer kalir."""
    t = pd.DataFrame(
        [_t("2026-01-05", f"A{i}", 1.0, gun_sayisi=10) for i in range(6)]
        + [_t("2026-01-06", f"B{i}", 1.0, gun_sayisi=10) for i in range(6)])
    out = apply_portfolio(t, None)
    gun2 = out[out["entry_date"] == pd.Timestamp("2026-01-06")]
    assert gun2["secildi"].sum() == 4


def test_secim_kurali_yuksek_siralamayi_secer():
    """Tavan 2'ye indirilir; momentum yuzdeligi yuksek olanlar secilir."""
    gun = pd.Timestamp("2026-01-05")
    t = pd.DataFrame([_t("2026-01-05", s, 1.0) for s in ("DUSUK", "ORTA",
                                                         "YUKSEK")])
    rank = pd.DataFrame({"DUSUK": [0.1], "ORTA": [0.5], "YUKSEK": [0.9]},
                        index=[gun])
    out = apply_portfolio(t, rank, gunluk=2)
    secilenler = set(out[out["secildi"]]["symbol"])
    assert secilenler == {"YUKSEK", "ORTA"}


def test_skoru_olmayan_aday_sona_atilir_ama_dislanmaz():
    """Siralamasi bilinmeyen sembol UYDURMA skorla one gecmez; yer
    varsa yine de alinir (veri yok != aday degil)."""
    gun = pd.Timestamp("2026-01-05")
    t = pd.DataFrame([_t("2026-01-05", s, 1.0) for s in ("BILINEN", "YOK")])
    rank = pd.DataFrame({"BILINEN": [0.9]}, index=[gun])
    tek = apply_portfolio(t, rank, gunluk=1)
    assert set(tek[tek["secildi"]]["symbol"]) == {"BILINEN"}
    iki = apply_portfolio(t, rank, gunluk=2)
    assert iki["secildi"].sum() == 2


def test_bos_tablo_cokmez():
    bos = pd.DataFrame(columns=["entry_date", "exit_date", "symbol", "r_net"])
    assert apply_portfolio(bos, None).empty


def test_f7_hukmu_tek_stratejide_iyilesmeyi_kabul_etmez():
    """Kural 4: en az IKI stratejide iyilesme. Bulgu 3 tek strateji
    (Donchian) uzerinden dogmustu - genellenebilirligi sinaniyor."""
    k = {"S1": {"secimli": {"islem": 200, "beklenti_R": 0.2},
                "taban": {"islem": 200, "beklenti_R": 0.05}},
         "S2": {"secimli": {"islem": 150, "beklenti_R": -0.1},
                "taban": {"islem": 150, "beklenti_R": 0.02}}}
    v = verdict_f7(k)
    assert v["iyilesen_stratejiler"] == ["S1"]
    assert v["kosullar"]["en az 2 stratejide iyilesme"] is False
    assert v["karar"].startswith("RED")


def test_f7_kucuk_orneklemde_red():
    k = {"S1": {"secimli": {"islem": 30, "beklenti_R": 0.2},
                "taban": {"islem": 30, "beklenti_R": 0.05}},
         "S2": {"secimli": {"islem": 40, "beklenti_R": 0.3},
                "taban": {"islem": 40, "beklenti_R": 0.1}}}
    v = verdict_f7(k)
    assert v["kosullar"]["secilen islem >= 100"] is False
    assert v["karar"].startswith("RED")


def test_f7_on_sartlar_dolunca_aday_der_ama_hukum_vermez():
    """Alet KENDI BASINA 'kabul' demez - dort kosulun ayrintisi
    incelenmeli (yari-donem tutarliligi compare ciktisindan okunur)."""
    k = {"S1": {"secimli": {"islem": 200, "beklenti_R": 0.2},
                "taban": {"islem": 200, "beklenti_R": 0.05}},
         "S2": {"secimli": {"islem": 150, "beklenti_R": 0.1},
                "taban": {"islem": 150, "beklenti_R": 0.02}}}
    v = verdict_f7(k)
    assert v["karar"].startswith("ADAY")
    assert "DORT kosul" in v["not"]
