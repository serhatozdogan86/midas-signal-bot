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
import os
from pathlib import Path

import pandas as pd

BT_DIR = Path(os.environ.get("BT_DIR", "research/_data"))
PKL = BT_DIR / "daily.pkl"
UNIVERSE_TXT = Path("data/static_universe.txt")
BENCH = "SPY"


def universe() -> list[str]:
    """Statik evren + SPY (rejim/rezidüel icin gerekli)."""
    syms = [ln.strip() for ln in UNIVERSE_TXT.read_text().splitlines()
            if ln.strip() and not ln.startswith("#")]
    if BENCH not in syms:
        syms.append(BENCH)
    return syms


def download(years: int = 2) -> pd.DataFrame:
    import yfinance as yf                      # yalniz indirirken gerekir
    syms = universe()
    print(f"indiriliyor: {len(syms)} sembol, {years} yil")
    raw = yf.download(syms, period=f"{years}y", interval="1d",
                      progress=False, auto_adjust=False, group_by="column")
    if raw is None or raw.empty:
        raise RuntimeError("veri gelmedi - ag/saglayici sorunu. "
                           "Bos onbellek YAZILMAZ (2.1).")
    got = {s for s in syms if ("Close", s) in raw.columns
           and raw[("Close", s)].notna().any()}
    eksik = sorted(set(syms) - got)
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
