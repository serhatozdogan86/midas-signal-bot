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


def download(years: int = 2) -> pd.DataFrame:
    import yfinance as yf                      # yalniz indirirken gerekir
    syms, kaynak = universe()
    harita = to_yahoo(syms)                    # yahoo_sembol -> depo_sembolu
    print(f"indiriliyor: {len(syms)} sembol, {years} yil (evren: {kaynak})")
    raw = yf.download(list(harita), period=f"{years}y", interval="1d",
                      progress=False, auto_adjust=False, group_by="column")
    if raw is None or raw.empty:
        raise RuntimeError("veri gelmedi - ag/saglayici sorunu. "
                           "Bos onbellek YAZILMAZ (2.1).")
    got = {s for s in harita if ("Close", s) in raw.columns
           and raw[("Close", s)].notna().any()}
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
    return raw


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
