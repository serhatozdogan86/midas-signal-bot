"""PORTFOY KATMANI ve SECIM KURALI (Faz 4 / F7).

Harness her sembolu BAGIMSIZ simule eder: "sinyal varsa isleme gir".
Gercek hayatta oyle olmuyor - ayni gun 20 aday dogabilir, sermaye ve
dikkat sinirli, bot da tavan uyguluyor (gunluk <=6, eszamanli <=10).
Yani gercek soru "hangi strateji" degil, "ayni gun hangi ADAYI secersin".

DEPO BULGUSU 3 (research-log): "portfoy tavani zararli DEGIL; SECIM
KURALI belirleyici - kaliteye gore secim Donchian'i -787R'den +11.8R'ye
tasidi." Bu modul o bulguyu YENIDEN URETILEBILIR hale getirir; onceki
olcum kapanmis bir analiz ortamindaydi (F6'da ogrendigimiz ders).

ON-KAYITLI KARAR KURALI (F7) - 8 Eyl 2026, SONUCLARA BAKILMADAN:
Momentum agirlikli secim, KILIT-3 tasarimina ancak DORDU BIRDEN
saglanirsa girer:
  1. secilen islem sayisi >= 100 (yoksa hukum yok, olcum surer)
  2. secimli net beklenti > tavan-var-secim-yok tabanindan YUKSEK
     (taban: ayni tavan, aday siralamasi yerine ilk-gelen)
  3. isaret iki yari donemde de ayni (v3.19 usulu tutarlilik sinavi)
  4. en az IKI stratejide birden iyilestirme (tek stratejide cikan
     fark, o stratejinin kendine ozgu davranisi olabilir)
Kural 4 bilincli olarak serttir: bulgu 3'un kendisi tek strateji
(Donchian) uzerinden dogmustu; genellenebilir mi, onu sinariz.

TAVAN TANIMI canli botla hizali (config-lock): gunluk <=6 yeni giris,
eszamanli <=10 acik pozisyon. Tavan DEGISTIRILMEZ - olculen sey tavan
degil, tavanin altinda KIMI sectigimiz.
"""
from __future__ import annotations

import pandas as pd

GUNLUK_TAVAN = 6
ESZAMANLI_TAVAN = 10


def apply_portfolio(trades: pd.DataFrame, rank: pd.DataFrame | None = None,
                    gunluk: int = GUNLUK_TAVAN,
                    eszamanli: int = ESZAMANLI_TAVAN) -> pd.DataFrame:
    """Tavanli portfoy simulasyonu.

    trades: entry_date, exit_date, symbol, r_net kolonlari.
    rank:   tarih x sembol yuzdelik tablosu (12-1 momentum). None ise
            SECIM KURALI YOK - adaylar ilk-gelen sirasiyla alinir
            (kiyas tabani; "tavan var ama secim yok" dunyasi).

    Doner: alinan islemler + 'secildi' bayragi tasiyan tam tablo.
    Elenen islem SILINMEZ, isaretlenir - kacan kazanci da olcebilelim
    (F4b'nin ayni refleksi: gorunmeyeni gorunur birak).
    """
    if trades.empty:
        return trades.assign(secildi=pd.Series(dtype=bool))
    t = trades.sort_values(["entry_date", "symbol"]).copy()
    t["secildi"] = False
    acik: list[pd.Timestamp] = []          # acik pozisyonlarin cikis gunleri
    for gun, grup in t.groupby("entry_date", sort=True):
        acik = [c for c in acik if c > gun]          # kapananlari dus
        yer = min(gunluk, eszamanli - len(acik))
        if yer <= 0:
            continue
        adaylar = list(grup.index)
        if rank is not None:
            def _skor(i: int) -> float:
                sym = t.at[i, "symbol"]
                try:
                    v = rank.at[gun, sym]
                except KeyError:
                    return -1.0                      # skoru olmayan aday SONA
                return -1.0 if pd.isna(v) else float(v)
            adaylar.sort(key=_skor, reverse=True)
        secilen = adaylar[:yer]
        t.loc[secilen, "secildi"] = True
        acik.extend(t.loc[secilen, "exit_date"].tolist())
    return t


def compare(trades: pd.DataFrame, rank: pd.DataFrame,
            label: str = "") -> dict:
    """Ayni islem havuzunda iki dunya: secim kurali VAR / YOK.

    21 Eyl eklemesi: kosul 3 (yari-donem tutarliligi) icin YARILAR da
    buradan doner. Ilk surumde bu hesap hic yapilmiyordu ve verdict_f7
    "ayrintiya bak" deyip birakiyordu - yani dort sartli kuralin yarisi
    olculmuyordu. Kural degismedi, EKSIK UYGULAMA tamamlandi.
    """
    from research.harness import halves, metrics
    secimli = apply_portfolio(trades, rank)
    tabani = apply_portfolio(trades, None)
    s_alinan = secimli[secimli["secildi"]]
    t_alinan = tabani[tabani["secildi"]]
    a = metrics(s_alinan, f"{label} secimli")
    b = metrics(t_alinan, f"{label} taban")
    out = {"secimli": a, "taban": b,
           "elenen_secimli": int((~secimli["secildi"]).sum()),
           "elenen_taban": int((~tabani["secildi"]).sum())}
    if len(s_alinan) >= 2 and len(t_alinan) >= 2:
        sy1, sy2 = halves(s_alinan)
        ty1, ty2 = halves(t_alinan)
        # Tutarlilik: secimin TABANA USTUNLUGU her iki yarida da ayni
        # yonde mi? ("secimli pozitif mi" degil - F7'nin sorusu
        # "secim fark yaratiyor mu", "strateji karli mi" degil.)
        f1 = sy1.get("beklenti_R", 0) - ty1.get("beklenti_R", 0)
        f2 = sy2.get("beklenti_R", 0) - ty2.get("beklenti_R", 0)
        out["yarilar"] = {"ilk_fark": round(f1, 3), "ikinci_fark": round(f2, 3),
                          "tutarli": bool((f1 > 0) == (f2 > 0))}
    return out


def verdict_f7(karsilastirmalar: dict[str, dict]) -> dict:
    """F7 hukmu - DORT sart da olculur (21 Eyl'de tamamlandi).

    ILK SURUMUN EKSIGI (21 Eyl saha kosumunda goruldu): yalniz kosul 1
    ve 4 hesaplaniyordu; 2 ve 3 icin "ayrintiya bak" deniyordu. Boyle
    bir hukum "ADAY" der ve karar gercekte hic verilmez. Kural
    DEGISMEDI - 8 Eyl'de yazilan dort sart aynen; eksik olan UYGULAMAYDI.

    KOSUL 2'NIN OKUNMASI - burada bir belirsizlik vardi ve acikca
    yaziyorum: 8 Eyl metni "secimli net beklenti > taban" diyor ama
    COK STRATEJILI kurulumda "hangi beklenti" belirtilmemis. 21 Eyl'de
    sabitlenen okuma: STRATEJI BASINA farklarin ORTALAMASI > 0, yani
    "secim ortalamada yardim ediyor mu". Tek bir strateji secilerek
    (orn. yalniz bizim vekil) sonucu istenen yone cevirmek mumkun
    olmasin diye ortalama kullaniliyor.
    Duyarlilik: alternatif okumalar da RAPORLANIR (okuma_duyarliligi),
    boylece "hangi okumayla gecerdi" sessizce secilemez.

    KOSUL 3: secimin TABANA USTUNLUGU iki yari donemde de ayni yonde
    olmali (compare() hesaplar). Sart, iyilesen stratejilerin
    COGUNLUGUNDA saglanmali - tek bir stratejinin tutarliligi tum
    kurali tasiyamaz (kosul 4'un ayni gerekcesi).
    """
    iyilesen, kotulesen, toplam_secilen, farklar = [], [], 0, []
    tutarli_sayisi = eslenen = 0
    for ad, k in karsilastirmalar.items():
        s, t = k["secimli"], k["taban"]
        if not s.get("islem") or not t.get("islem"):
            continue
        toplam_secilen += s["islem"]
        fark = s["beklenti_R"] - t["beklenti_R"]
        farklar.append(fark)
        (iyilesen if fark > 0 else kotulesen).append(ad)
        y = k.get("yarilar")
        if fark > 0 and y is not None:
            eslenen += 1
            tutarli_sayisi += 1 if y["tutarli"] else 0
    ort_fark = round(sum(farklar) / len(farklar), 4) if farklar else 0.0
    kosul = {
        "1. secilen islem >= 100": bool(toplam_secilen >= 100),
        "2. secim ortalamada yardim ediyor": bool(ort_fark > 0),
        "3. iyilesenlerin cogunlugu iki yarida tutarli":
            bool(eslenen and tutarli_sayisi * 2 > eslenen),
        "4. en az 2 stratejide iyilesme": bool(len(iyilesen) >= 2),
    }
    gecti = all(kosul.values())
    return {"iyilesen_stratejiler": iyilesen,
            "kotulesen_stratejiler": kotulesen,
            "toplam_secilen": toplam_secilen,
            "ortalama_fark_R": ort_fark,
            "tutarlilik": {"olculen": eslenen, "tutarli": tutarli_sayisi},
            "kosullar": kosul,
            "okuma_duyarliligi": {
                "kosul2_ortalama_fark": bool(ort_fark > 0),
                "kosul2_cogunluk_iyilesme":
                    bool(len(iyilesen) > len(kotulesen)),
                "not": ("Kosul 2'nin iki mesru okunusu; hukum ORTALAMA "
                        "okumasiyla verilir (21 Eyl'de sabitlendi), digeri "
                        "seffaflik icin raporlanir."),
            },
            "karar": ("KILIT-3 TASARIMINA GIRER (dort sart da saglandi)"
                      if gecti else "RED - dort sartin hepsi saglanmadi")}
