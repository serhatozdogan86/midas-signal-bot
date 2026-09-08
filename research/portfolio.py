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
    """Ayni islem havuzunda iki dunya: secim kurali VAR / YOK."""
    from research.harness import metrics
    secimli = apply_portfolio(trades, rank)
    tabani = apply_portfolio(trades, None)
    a = metrics(secimli[secimli["secildi"]], f"{label} secimli")
    b = metrics(tabani[tabani["secildi"]], f"{label} taban")
    return {"secimli": a, "taban": b,
            "elenen_secimli": int((~secimli["secildi"]).sum()),
            "elenen_taban": int((~tabani["secildi"]).sum())}


def verdict_f7(karsilastirmalar: dict[str, dict]) -> dict:
    """F7 hukmu - kural yukarida, SONUCLARA BAKILMADAN yazildi.
    karsilastirmalar: {strateji_adi: compare(...) ciktisi}."""
    iyilesen, toplam_secilen = [], 0
    for ad, k in karsilastirmalar.items():
        s, t = k["secimli"], k["taban"]
        if not s.get("islem") or not t.get("islem"):
            continue
        toplam_secilen += s["islem"]
        if s["beklenti_R"] > t["beklenti_R"]:
            iyilesen.append(ad)
    kosul = {
        "secilen islem >= 100": bool(toplam_secilen >= 100),
        "en az 2 stratejide iyilesme": bool(len(iyilesen) >= 2),
    }
    return {"iyilesen_stratejiler": iyilesen,
            "toplam_secilen": toplam_secilen,
            "kosullar": kosul,
            "not": ("Yari-donem tutarliligi (kosul 3) ve taban ustunlugu "
                    "strateji basina compare() ciktisindan okunur; hukum "
                    "ancak DORT kosul birden saglanirsa 'KILIT-3 tasarimina "
                    "girer' olur."),
            "karar": ("ADAY: dort kosul icin ayrinti incelenmeli"
                      if all(kosul.values()) else "RED - on sartlar dolmadi")}
