"""Zarar anatomisi (Faz 4 / F1) - olcunun kendisi test edilir.

Sayilar sahadan gelmeden yazildi (1 Eyl 2026). Test edilen sey
"neden kaybediyoruz"un CEVABI degil, cevabi uretecek aletin dogru
calisip calismadigi: MFE/MAE tanimi, Q1 esikleri, setup bayragi,
short kuralinin on-kayitli haliyle uygulanmasi.
"""
from __future__ import annotations

from app.services.loss_anatomy import (breakdown, excursions, q1_arms,
                                       q1_entry_or_exit, q2_setup_flags,
                                       q3_short_verdict)


def test_mfe_mae_tasarim_riski_birimiyle():
    """LONG, dolum 100, stop 98 -> risk 2. Fiyat 103'e cikip 97'ye
    inmisse MFE=+1.5R, MAE=-1.5R."""
    mfe, mae = excursions("LONG", 100.0, 98.0, [101.0, 103.0], [99.0, 97.0])
    assert mfe == 1.5 and mae == -1.5


def test_short_tarafta_yonler_ters():
    mfe, mae = excursions("SHORT", 100.0, 102.0, [101.0, 103.0], [97.0])
    assert mfe == 1.5      # fiyat dustu = SHORT lehine
    assert mae == -1.5


def test_mum_yoksa_none_doner():
    """'Mum yok' ile 'hic lehte gitmedi' ayni sey degil (2.1)."""
    assert excursions("LONG", 100.0, 98.0, [], []) == (None, None)
    assert excursions("LONG", None, 98.0, [101.0], [99.0]) == (None, None)
    assert excursions("LONG", 100.0, 100.0, [101.0], [99.0]) == (None, None)


def test_q1_cikis_sorunu_der():
    """Zararlar stop'a carpmadan once 1R+ kazandirmissa: cikis sorunu."""
    z = [{"mfe": m} for m in (1.2, 0.9, 1.5, 0.8, 1.1, 2.0, 0.95, 1.3,
                              1.0, 1.4)]
    r = q1_entry_or_exit(z)
    assert r["medyan_mfe"] >= 0.8
    assert "CIKIS/STOP" in r["hukum"]
    assert r["dayaniklilik"]["saglam"] is True


def test_q1_giris_sorunu_der():
    """Zararlar hic lehte gitmemisse: giris/secim sorunu."""
    z = [{"mfe": m} for m in (0.1, 0.0, 0.25, 0.2, 0.05, 0.3, 0.15, 0.1,
                              0.2, 0.0)]
    r = q1_entry_or_exit(z)
    assert "GIRIS/SECIM" in r["hukum"]


def test_q1_arada_kalirsa_tek_hukum_verilmez():
    r = q1_entry_or_exit([{"mfe": m} for m in (0.5, 0.55, 0.6)])
    assert "KARISIK" in r["hukum"]


def test_q1_kucuk_orneklem_zayif_damgasi_yer():
    """Hukum verilse bile n<10 ise 'yon isareti' denir (anatomi
    aletinin 1 Eyl dersi burada da uygulanir)."""
    r = q1_entry_or_exit([{"mfe": 1.2}, {"mfe": 1.5}, {"mfe": 0.9}])
    assert "CIKIS/STOP" in r["hukum"]
    assert r["dayaniklilik"]["saglam"] is False


def test_q1_olculebilir_zarar_yoksa_hukum_yok():
    assert q1_entry_or_exit([{"mfe": None}])["hukum"].startswith("HUKUM YOK")


def test_breakdown_bilinmeyen_grubu_atmaz():
    """Alan bos olan kayit sessizce dusurulmez - '(bilinmiyor)' altinda
    gorunur; yoksa toplamlar tutmaz ve kayip veri gizlenir."""
    g = breakdown([{"setup_type": "BREAKOUT", "r": -1.0},
                   {"setup_type": None, "r": 2.0}], "setup_type")
    adlar = {x["grup"]: x for x in g}
    assert adlar["(bilinmiyor)"]["n"] == 1
    assert adlar["BREAKOUT"]["net_r"] == -1.0


def test_q2_setup_bayragi_iki_sarta_birden_bakar():
    """n>=5 VE net-R<=-3.0. Tek sart yetmez."""
    cok_zararli_ama_az = [{"setup_type": "A", "r": -2.0} for _ in range(2)]
    yeterli_ama_hafif = [{"setup_type": "B", "r": -0.2} for _ in range(6)]
    ikisi_de = [{"setup_type": "C", "r": -1.0} for _ in range(5)]
    bayrak = q2_setup_flags(cok_zararli_ama_az + yeterli_ama_hafif + ikisi_de)
    assert [g["grup"] for g in bayrak] == ["C"]


def test_q3_short_kurali_on_kayitli_haliyle():
    """n<20 iken hukum YOK - negatif olsa bile (30 Tem on-kaydi)."""
    az = [{"direction": "SHORT", "r": -1.0} for _ in range(19)]
    assert "HENUZ HUKUM YOK" in q3_short_verdict(az)["hukum"]
    yeterli = [{"direction": "SHORT", "r": -1.0} for _ in range(20)]
    assert "KURAL TETIKLENDI" in q3_short_verdict(yeterli)["hukum"]
    pozitif = [{"direction": "SHORT", "r": 1.0} for _ in range(20)]
    assert "tetiklenmedi" in q3_short_verdict(pozitif)["hukum"]


def test_q3_long_kayitlari_short_hukmune_karismaz():
    karisik = ([{"direction": "LONG", "r": -5.0} for _ in range(30)]
               + [{"direction": "SHORT", "r": 1.0} for _ in range(20)])
    r = q3_short_verdict(karisik)
    assert r["n"] == 20 and r["net_r"] == 20.0


# --- Q1 devami: iki kol (18 Eyl saha kosumu 'KARISIK' verdi) ---------

def _z(mfe: float, r: float = -1.0) -> dict:
    return {"mfe": mfe, "r": r}


def test_kollar_q1_esikleriyle_ayni_sinirlari_kullanir():
    """Yeni esik UYDURULMADI: soguk <=0.3, sicak >=0.8 - Q1'in kendi
    sinirlari. 0.3 ve 0.8 sinirlari KENDI kollarina dahildir."""
    k = q1_arms([_z(0.3), _z(0.31), _z(0.79), _z(0.8)])
    assert k["soguk"]["n"] == 1
    assert k["ara"]["n"] == 2
    assert k["sicak"]["n"] == 1


def test_sicak_kol_baskinsa_cikis_tasarimi_gundeme():
    """Pay >= %40 VE sicak kolun zarari toplamin yarisindan buyuk."""
    k = q1_arms([_z(1.5, -2.0), _z(2.0, -2.0), _z(1.2, -2.0),
                 _z(0.1, -0.5), _z(0.0, -0.5)])
    assert k["sicak"]["pay_%"] == 60.0
    assert "SICAK KOL BASKIN" in k["hukum"]


def test_sicak_kol_kucukse_giris_baskin():
    z = [_z(0.05, -1.0) for _ in range(9)] + [_z(1.5, -1.0)]
    k = q1_arms(z)
    assert k["sicak"]["pay_%"] == 10.0
    assert "GIRIS/SECIM BASKIN" in k["hukum"]


def test_pay_yetse_de_R_yetmezse_tek_suclu_ilan_edilmez():
    """Kural IKI sarta birden bakar: sicak kol islem sayisinda buyuk
    ama zararin yarisindan azini tasiyorsa hukum 'ARADA'dir.
    Gerekce: 'kac islem' ile 'kac R' farkli sorulardir."""
    k = q1_arms([_z(1.5, -0.2), _z(1.6, -0.2), _z(0.0, -5.0)])
    assert k["sicak"]["pay_%"] > 40
    assert "ARADA" in k["hukum"]


def test_kol_raporu_olculebilir_kayit_yoksa_hukum_vermez():
    assert q1_arms([{"mfe": None}])["hukum"].startswith("HUKUM YOK")
