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
    assert v["kosullar"]["4. en az 2 stratejide iyilesme"] is False
    assert v["karar"].startswith("RED")


def test_f7_kucuk_orneklemde_red():
    k = {"S1": {"secimli": {"islem": 30, "beklenti_R": 0.2},
                "taban": {"islem": 30, "beklenti_R": 0.05}},
         "S2": {"secimli": {"islem": 40, "beklenti_R": 0.3},
                "taban": {"islem": 40, "beklenti_R": 0.1}}}
    v = verdict_f7(k)
    assert v["kosullar"]["1. secilen islem >= 100"] is False
    assert v["karar"].startswith("RED")


def test_f7_on_sartlar_dolunca_aday_der_ama_hukum_vermez():
    """Alet KENDI BASINA 'kabul' demez - dort kosulun ayrintisi
    incelenmeli (yari-donem tutarliligi compare ciktisindan okunur)."""
    k = {"S1": {"secimli": {"islem": 200, "beklenti_R": 0.2},
                "taban": {"islem": 200, "beklenti_R": 0.05}},
         "S2": {"secimli": {"islem": 150, "beklenti_R": 0.1},
                "taban": {"islem": 150, "beklenti_R": 0.02}}}
    v = verdict_f7(k)
    # yarilar verilmedigi icin kosul 3 olculemez -> RED (sessizce
    # gecmez: olculemeyen sart SAGLANMIS sayilmaz, 2.2 refleksi)
    assert v["kosullar"]["3. iyilesenlerin cogunlugu iki yarida tutarli"] is False
    assert v["karar"].startswith("RED")


# --- compare() butunu: secim gercekten fark yaratiyor mu? ------------

def _havuz(kazanan_ust: bool) -> tuple:
    """30 gun x 8 aday. kazanan_ust=True ise momentum siralamasinda
    USTTE olanlar kazaniyor; False ise tam tersi."""
    gunler = pd.bdate_range("2026-01-05", periods=30)
    satirlar, rank_satir = [], {}
    for g in gunler:
        for j in range(8):
            iyi = (j >= 5) if kazanan_ust else (j < 3)
            satirlar.append({"entry_date": g,
                             "exit_date": g + pd.Timedelta(days=2),
                             "symbol": f"S{j}",
                             "r_net": 1.0 if iyi else -0.5, "bars_held": 2})
        # yuksek j = yuksek yuzdelik (alfabetik sira ile TERS)
        rank_satir[g] = {f"S{j}": (j + 1) / 8 for j in range(8)}
    return pd.DataFrame(satirlar), pd.DataFrame(rank_satir).T


def test_secim_kurali_taban_ile_ayni_sonucu_vermez():
    """20 Eyl dersi: ilk duman testimde siralama alfabetik sirayla
    ORTUSUYORDU, iki dunya ayni kumeyi secti ve fark sifir cikti -
    'kural var' sanmak tuzagi. Seri artik bilerek ters kuruluyor:
    momentumun USTundekiler kazaniyor ama alfabetik olarak SONdalar."""
    from research.portfolio import compare
    t, rank = _havuz(kazanan_ust=True)
    k = compare(t, rank, label="T")
    assert k["secimli"]["islem"] == k["taban"]["islem"]      # ayni tavan
    assert k["secimli"]["beklenti_R"] > k["taban"]["beklenti_R"]
    assert k["secimli"]["beklenti_R"] > 0 > k["taban"]["beklenti_R"]


def test_siralama_yanlis_yondeyse_taban_kazanir():
    """Simetri sinavi: secim kurali her zaman iyi degildir. Kazananlar
    siralamanin ALTINDAYSA momentumla secmek ZARAR ettirir - alet bunu
    da gosterebilmeli, yoksa yalniz istedigimizi gosteren bir ayna
    olurdu."""
    from research.portfolio import compare
    t, rank = _havuz(kazanan_ust=False)
    k = compare(t, rank, label="T")
    assert k["secimli"]["beklenti_R"] < k["taban"]["beklenti_R"]


# --- dort sartin tamami (21 Eyl: eksik uygulama tamamlandi) ----------

def _k(secimli_b, taban_b, islem=200, y1=None, y2=None):
    d = {"secimli": {"islem": islem, "beklenti_R": secimli_b},
         "taban": {"islem": islem, "beklenti_R": taban_b}}
    if y1 is not None:
        d["yarilar"] = {"ilk_fark": y1, "ikinci_fark": y2,
                        "tutarli": (y1 > 0) == (y2 > 0)}
    return d


def test_dort_sart_saglaninca_kilit3e_girer():
    v = verdict_f7({"A": _k(0.20, 0.05, y1=0.1, y2=0.2),
                    "B": _k(0.10, 0.02, y1=0.05, y2=0.09)})
    assert all(v["kosullar"].values())
    assert v["karar"].startswith("KILIT-3")


def test_yarilar_tutarsizsa_red():
    """Iyilesme tek yaridan geliyorsa kural GECMEZ - v3.19 usulu."""
    v = verdict_f7({"A": _k(0.20, 0.05, y1=0.4, y2=-0.1),
                    "B": _k(0.10, 0.02, y1=0.3, y2=-0.2)})
    assert v["kosullar"]["4. en az 2 stratejide iyilesme"] is True
    assert v["kosullar"]["3. iyilesenlerin cogunlugu iki yarida tutarli"] is False
    assert v["karar"].startswith("RED")


def test_ortalama_negatifse_red_iki_strateji_iyilesse_bile():
    """21 Eyl saha vakasinin sekli: bazi stratejiler iyilesirken
    baskalari COK kotulesebilir. Kosul 2 ortalamaya bakar; iki
    stratejide iyilesme tek basina yetmez."""
    v = verdict_f7({"A": _k(0.05, 0.01, y1=0.02, y2=0.06),
                    "B": _k(0.04, 0.01, y1=0.02, y2=0.04),
                    "C": _k(-0.50, -0.10, y1=-0.3, y2=-0.5)})
    assert v["kosullar"]["4. en az 2 stratejide iyilesme"] is True
    assert v["ortalama_fark_R"] < 0
    assert v["kosullar"]["2. secim ortalamada yardim ediyor"] is False
    assert v["karar"].startswith("RED")


def test_okuma_duyarliligi_iki_okumayi_da_raporlar():
    """Kosul 2'nin iki mesru okunusu ayri ayri gorunur - 'hangi
    okumayla gecerdi' sessizce secilemesin."""
    v = verdict_f7({"A": _k(0.05, 0.01, y1=0.02, y2=0.06),
                    "B": _k(0.04, 0.01, y1=0.02, y2=0.04),
                    "C": _k(-0.50, -0.10, y1=-0.3, y2=-0.5)})
    d = v["okuma_duyarliligi"]
    assert d["kosul2_ortalama_fark"] is False      # ortalama negatif
    assert d["kosul2_cogunluk_iyilesme"] is True   # 2 iyilesen > 1 kotulesen


def test_compare_yarilari_uretir():
    """compare() artik yari-donem farkini da dondurur (kosul 3'un
    girdisi). Ilk surumde bu hesap HIC yapilmiyordu."""
    from research.portfolio import compare
    t, rank = _havuz(kazanan_ust=True)
    k = compare(t, rank, label="T")
    assert "yarilar" in k
    assert k["yarilar"]["tutarli"] is True
