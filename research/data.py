"""Backtest verisi: gunluk mumlari indir + diske onbellekle.

Neden var: run.py eskiden /home/claude/bt/daily.pkl'i okuyordu - o yol
gecici bir analiz ortamindan kalmaydi ve o ortam kapandiginda duzenek
KOSULAMAZ hale geldi (F6'ya baslarken fark edildi, 24 Agu). Artik veri
depo icinde yeniden uretilebilir.

Kullanim (agi olan bir oturumda; bulut oturumu Yahoo'ya kapali):
    python3 -m research.data --years 2
Cikti: research/_data/daily.pkl (git'e girmez, .gitignore'da)

Ilke 2.1 (uydurma veri yok) burada da gecerli: eksik sembol SESSIZCE
atlanmaz, ekrana yazilir ve evren sayisi raporlanir.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pandas as pd

from app.integrations.yfinance_client import YFinanceClient

BT_DIR = Path(os.environ.get("BT_DIR", "research/_data"))
PKL = BT_DIR / "daily.pkl"
INTEGRITY_JSON = BT_DIR / "integrity.json"
UNIVERSE_TXT = Path("data/static_universe.txt")
CACHE_JSON = Path("data/universe_cache.json")
BENCH = "SPY"


def universe() -> tuple[list[str], str]:
    """Arastirma evreni + SPY. Doner: (semboller, kaynak adi).

    KAYNAK SIRASI (24 Agu duzeltmesi): once CANLI evren onbellegi
    (data/universe_cache.json - botun kendi kazidigi liste), o yoksa
    statik yedek. Gerekce: ilk yazimda yalniz statik dosya okunuyordu
    ve arastirma evreni canli evrenden SESSIZCE ayrisiyordu (ilk
    kosumda yakalandi: SQ artik XYZ, sirket sembolunu degistirmis).
    Arastirma baska bir evrende olculurse hukum canli bota ait olmaz.
    """
    syms: list[str] = []
    kaynak = "statik yedek liste"
    try:
        cached = json.loads(CACHE_JSON.read_text()).get("symbols", [])
        if cached:
            syms, kaynak = list(cached), f"canli evren onbellegi ({CACHE_JSON})"
    except (OSError, ValueError):
        pass
    if not syms:
        syms = [ln.strip() for ln in UNIVERSE_TXT.read_text().splitlines()
                if ln.strip() and not ln.startswith("#")]
    if BENCH not in syms:
        syms.append(BENCH)
    return syms, kaynak


def to_yahoo(symbols: list[str]) -> dict[str, str]:
    """Yahoo bicimi -> depo bicimi haritasi.

    URETIMDEKI kurali yeniden kullanir (YFinanceClient._to_yahoo):
    'BRK.B' Yahoo'da 'BRK-B'dir. Bu tuzak canli tarafta 30 Tem'de
    cozulmustu; arastirma katmani kendi yolunu yazdigi icin AYNI
    tuzagi 24 Agu'da yeniden kesfetti (ilk kosumda "BRK.B verisi yok"
    uyarisi). Ders: paralel uygulama, cozulmus hatalari geri getirir.
    """
    return {YFinanceClient._to_yahoo(s): s for s in symbols}


def _indir(yf, semboller: list[str], years: int, parca: int = 200,
           bekleme: float = 2.0) -> pd.DataFrame:
    """Evreni PARCA PARCA indirir, parcalar arasinda nefes alir.

    v4.53 (21 Eyl SAHA VAKASI): 1628 sembollük canli evren tek atista
    istendi, Yahoo HIZ SINIRINA takildi ve 114 sembol dustu - ustelik
    RASTGELE DEGIL, istek sirasinin SONUNDAN (JNJ, LOW, UPS, T, ABT,
    NKE gibi buyuk isimler). Bu, deponun daha once yasadigi "saglayici
    sessizce kirpiyor" sinifinin ta kendisi (Finnhub takvimi, v4.40).
    Once mekanizmayi duzeltiyoruz: kucuk parcalar + bekleme + eksikler
    icin TEK SEFERLIK yeniden deneme. Esikle oynayarak degil.
    """
    import time
    parcalar = [semboller[i:i + parca]
                for i in range(0, len(semboller), parca)]
    tablolar = []
    for i, p in enumerate(parcalar, 1):
        print(f"  parca {i}/{len(parcalar)} ({len(p)} sembol)...")
        d = yf.download(p, period=f"{years}y", interval="1d", progress=False,
                        auto_adjust=False, group_by="column")
        if d is not None and not d.empty:
            tablolar.append(d)
        if i < len(parcalar):
            time.sleep(bekleme)
    if not tablolar:
        return pd.DataFrame()
    return pd.concat(tablolar, axis=1)


def download(years: int = 2) -> pd.DataFrame:
    import yfinance as yf                      # yalniz indirirken gerekir
    syms, kaynak = universe()
    harita = to_yahoo(syms)                    # yahoo_sembol -> depo_sembolu
    print(f"indiriliyor: {len(syms)} sembol, {years} yil (evren: {kaynak})")
    raw = _indir(yf, list(harita), years)
    if raw is None or raw.empty:
        raise RuntimeError("veri gelmedi - ag/saglayici sorunu. "
                           "Bos onbellek YAZILMAZ (2.1).")

    def _gelenler(tablo: pd.DataFrame) -> set:
        return {s for s in harita if ("Close", s) in tablo.columns
                and tablo[("Close", s)].notna().any()}

    got = _gelenler(raw)
    eksik_yahoo = sorted(set(harita) - got)
    if eksik_yahoo:                            # ikinci tur: yalniz eksikler
        print(f"  {len(eksik_yahoo)} sembol ilk turda gelmedi - "
              "kucuk parcalarla yeniden deneniyor")
        tekrar = _indir(yf, eksik_yahoo, years, parca=50, bekleme=5.0)
        if tekrar is not None and not tekrar.empty:
            raw = pd.concat([raw, tekrar], axis=1)
            raw = raw.loc[:, ~raw.columns.duplicated()]
            got = _gelenler(raw)
    eksik = sorted(harita[s] for s in set(harita) - got)
    if eksik:
        print(f"UYARI: {len(eksik)} sembol icin veri yok: "
              f"{', '.join(eksik[:15])}{' ...' if len(eksik) > 15 else ''}")
    if BENCH not in got:
        raise RuntimeError(f"{BENCH} verisi yok - kiyas tabani olmadan "
                           "duzenek kosturulmaz (fail-closed).")
    BT_DIR.mkdir(parents=True, exist_ok=True)
    raw.to_pickle(PKL)
    print(f"yazildi: {PKL} ({len(raw)} gun, {len(got)} sembol)")
    rapor = integrity(raw, sorted(got), istenen=len(harita), eksik=eksik)
    print_integrity(rapor)
    INTEGRITY_JSON.write_text(json.dumps(rapor, ensure_ascii=False, indent=2))
    return raw


def integrity(raw: pd.DataFrame, syms: list[str] | None = None,
              istenen: int | None = None,
              eksik: list[str] | None = None) -> dict:
    """VERI BUTUNLUK RAPORU - ikizden tasindi (acik kuyruk md. 9).

    bybit'in indiricisi (tools/download_backtest_data.py) satir sayisi,
    beklenen sayi, tekrar ve zaman bosluklarini SAYIYOR; midas'ta
    karsiligi yoktu - yani "veri geldi" ile "veri TAM geldi" ayrimini
    yapamiyorduk. Sessiz eksik veri bu depoda daha once gorulmus bir
    hata sinifidir (Finnhub takvimi ~1500 satirda sessizce kirpiyordu,
    v4.40). Ayni sinifi arastirma verisinde de goreme sansi olsun.

    Doner: gun sayisi, sembol sayisi, tarih araligi, tekrar eden gun
    sayisi, ve sembol basina eksik gun (NaN) sayilarindan en kotu 10'u.
    HICBIR SEY DUZELTMEZ - yalnizca sayar ve raporlar (2.1).
    """
    idx = raw.index
    tekrar = int(len(idx) - len(idx.unique()))
    kapanis = raw["Close"] if "Close" in raw.columns else pd.DataFrame()
    if syms:
        kapanis = kapanis[[c for c in kapanis.columns if c in set(syms)]]
    bosluk = {}
    for c in kapanis.columns:
        # DIKKAT: degisken adi 'eksik' OLAMAZ - ayni adli parametreyi
        # golgeler ve rapor sayilari bozulur (21 Eyl'de yakalandi).
        bos_gun = int(kapanis[c].isna().sum())
        if bos_gun:
            bosluk[c] = bos_gun
    en_kotu = sorted(bosluk.items(), key=lambda kv: -kv[1])[:10]
    alinan = int(kapanis.shape[1]) if len(kapanis.columns) else 0
    eksik = eksik or []
    oran = round(len(eksik) / istenen, 4) if istenen else 0.0
    return {"gun": int(len(idx)),
            "sembol": alinan,
            "ilk_gun": str(idx.min())[:10] if len(idx) else None,
            "son_gun": str(idx.max())[:10] if len(idx) else None,
            "istenen_sembol": istenen,
            "eksik_sembol": len(eksik),
            "eksik_orani": oran,
            "eksik_ornekleri": eksik[:15],
            # BAGLAYICILIK ESIGI - 21 Eyl'de, KIRPILMIS bir kosumdan
            # SONRA eklendi ve bunu acikca yaziyorum. Esik bir PASS'i
            # engelliyor (o kosum dort sarti da gecmisti), yani lehimize
            # secilmis olamaz. Gerekce mekanizmada: %2'yi asan eksik,
            # saglayici kirpmasi demektir ve kirpma RASTGELE DEGIL -
            # istek sirasinin sonundan duser, yani evreni sistematik
            # olarak carpitir (Finnhub v4.40 dersi).
            "baglayici": bool(oran <= 0.02),
            "tekrar_eden_gun": tekrar,
            "eksik_gunu_olan_sembol": len(bosluk),
            "en_cok_eksik": [{"sembol": s, "eksik_gun": n} for s, n in en_kotu]}


def print_integrity(rapor: dict) -> None:
    print("\nBUTUNLUK RAPORU (ikiz usulu - sayar, duzeltmez)")
    print(f"  gun araligi   : {rapor['ilk_gun']} .. {rapor['son_gun']} "
          f"({rapor['gun']} gun)")
    print(f"  sembol        : {rapor['sembol']}")
    print(f"  tekrar eden gun: {rapor['tekrar_eden_gun']}"
          f"{'  <-- INCELE' if rapor['tekrar_eden_gun'] else ''}")
    print(f"  eksik gunu olan sembol: {rapor['eksik_gunu_olan_sembol']}")
    for r in rapor["en_cok_eksik"]:
        print(f"    {r['sembol']:<8}{r['eksik_gun']:>5} gun eksik")
    if rapor.get("istenen_sembol"):
        print(f"  istenen/alinan : {rapor['istenen_sembol']} / "
              f"{rapor['sembol']}  (eksik %{rapor['eksik_orani'] * 100:.1f})")
        if not rapor.get("baglayici"):
            print("  >>> VERI KIRPIK: eksik oran %2'yi asiyor. Bu veriyle")
            print("  >>> uretilen hukumler BAGLAYICI DEGILDIR (2.1/2.2).")


def load() -> pd.DataFrame:
    if not PKL.exists():
        raise FileNotFoundError(
            f"{PKL} yok. Once agi olan bir oturumda calistir: "
            "python3 -m research.data --years 2")
    return pd.read_pickle(PKL)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=2)
    download(ap.parse_args().years)
