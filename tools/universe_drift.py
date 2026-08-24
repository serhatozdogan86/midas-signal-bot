"""EVREN KAYMASI DENETCISI - statik yedek liste vs canli evren (salt okur).

Neden var (24 Agu, F6 backtest'i): statik yedek liste canli evrenden
sessizce ayrismisti (SQ artik XYZ). Yedek liste ancak scrape VE cache
birlikte coktugunde devreye girer - yani en kotu gunde. O gun bayat bir
listeyle calismak, "yedek var" sanip yedeksiz kalmaktir.

Hicbir sey DEGISTIRMEZ, yalnizca rapor eder (2.1: eksik veri
gizlenmez). Haftalik bakim adimi olarak elle kosulur:

    python3 tools/universe_drift.py
    python3 tools/universe_drift.py --json     # makine okunur cikti

Cikis kodu: kayma yoksa 0, varsa 1 (ileride CI/bakim isine baglanabilir).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

STATIC = Path("data/static_universe.txt")
CACHE = Path("data/universe_cache.json")


def read_static(path: Path = STATIC) -> list[str]:
    return sorted({ln.strip().upper() for ln in
                   path.read_text(encoding="utf-8").splitlines()
                   if ln.strip() and not ln.startswith("#")})


def read_live(path: Path = CACHE) -> list[str] | None:
    """Canli evren onbellegi. YOKSA None doner - bos liste DEGIL.
    (Fark onemli: 'onbellek yok' ile 'evren bos' ayni sey degildir.)"""
    try:
        return sorted({s.upper() for s in
                       json.loads(path.read_text()).get("symbols", [])})
    except (OSError, ValueError):
        return None


def drift(static: list[str], live: list[str]) -> dict:
    """Iki listeyi karsilastirir. yalniz_statik = yedekte olup canlida
    olmayan (bayat olma adayi); yalniz_canli = canlida olup yedekte
    olmayan (yedek eksik kaliyor)."""
    s, c = set(static), set(live)
    return {"statik_sayi": len(s), "canli_sayi": len(c),
            "ortak": len(s & c),
            "yalniz_statik": sorted(s - c),
            "yalniz_canli": sorted(c - s)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    static = read_static()
    live = read_live()
    if live is None:
        print("ATLANDI: canli evren onbellegi yok "
              f"({CACHE}). Bot en az bir kez hazirlik taramasi yapmali.")
        return 0                                # kayma OLCULEMEDI, hata degil
    d = drift(static, live)
    if args.json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
    else:
        print(f"statik yedek : {d['statik_sayi']} sembol")
        print(f"canli evren  : {d['canli_sayi']} sembol")
        print(f"ortak        : {d['ortak']}")
        for baslik, anahtar in (("yedekte VAR, canlida YOK (bayat adayi)",
                                 "yalniz_statik"),
                                ("canlida VAR, yedekte YOK (yedek eksik)",
                                 "yalniz_canli")):
            liste = d[anahtar]
            print(f"\n{baslik}: {len(liste)}")
            if liste:
                print("  " + ", ".join(liste))
    return 1 if (d["yalniz_statik"] or d["yalniz_canli"]) else 0


if __name__ == "__main__":
    sys.exit(main())
