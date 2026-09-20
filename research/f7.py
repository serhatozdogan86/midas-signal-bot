"""F7 KOSTURUCUSU - secim kurali fark yaratiyor mu? (Faz 4)

Ne yapar: run.py'nin urettigi islem defterlerini (research/_data/
trades.pkl) alir, her strateji icin AYNI havuzu iki dunyada kosar -
adaylar momentum yuzdeligine gore SIRALANARAK secilince, ve siralama
olmadan (ilk-gelen) - sonra on-kayitli F7 kuralini uygular.

Kural portfolio.py'de yazili (8 Eyl, sonuclara BAKILMADAN) ve burada
DEGISTIRILMEZ; bu dosya yalnizca veriyi kurala goturur.

Kullanim (agi olan oturumda, once veri):
    python3 -m research.data --years 2     # daily.pkl
    python3 -m research.run                # trades.pkl (+ F6 hukmu)
    python3 -m research.f7                 # BU: F7 hukmu

NOT (F6 dersi): tavanlar canli botla ayni (gunluk <=6, eszamanli <=10)
ve DEGISTIRILMEZ. Olculen sey tavan degil, tavanin altinda kimi
sectigimiz.
"""
from __future__ import annotations

import sys

import pandas as pd

from research.data import BENCH, load
from research.portfolio import compare, verdict_f7

TRADES_PKL = "research/_data/trades.pkl"


def momentum_ranks(raw: pd.DataFrame) -> pd.DataFrame:
    """12-1 kesitsel momentum yuzdeligi (gun x sembol).

    run.py'dakiyle AYNI tanim - tek kanitli giris edge'i bu (bulgu 1).
    Ayri bir kopya yazmak yerine ayni formulu kullaniyoruz; farkli
    tanim, F7 hukmunu sessizce baska bir soruya cevirirdi.
    """
    close = raw["Close"]
    px = close[[c for c in close.columns if c != BENCH]]
    mom = px.shift(21) / px.shift(252) - 1      # son ay HARIC 12 ay
    return mom.rank(axis=1, pct=True)


def main() -> int:
    try:
        frames = pd.read_pickle(TRADES_PKL)
    except (OSError, ValueError) as exc:
        print(f"HATA: {TRADES_PKL} okunamadi ({exc}).")
        print("Once: python3 -m research.data --years 2 && python3 -m research.run")
        return 2
    rank = momentum_ranks(load())

    sonuc: dict[str, dict] = {}
    print("F7 - SECIM KURALI (momentum siralamasi) vs TABAN (ilk-gelen)")
    print("  tavanlar: gunluk <=6, eszamanli <=10 (canli botla ayni)\n")
    print(f"  {'strateji':<22}{'islem':>7}{'beklenti':>11}{'toplam R':>11}")
    for ad, t in sorted(frames.items()):
        if t is None or t.empty:
            continue
        k = compare(t, rank, label=ad)
        sonuc[ad] = k
        for etiket, m in (("secimli", k["secimli"]), ("taban", k["taban"])):
            if not m.get("islem"):
                continue
            print(f"  {ad[:18] + ' ' + etiket:<22}{m['islem']:>7}"
                  f"{m['beklenti_R']:>11.3f}{m['toplam_R']:>11.1f}")

    v = verdict_f7(sonuc)
    print("\n=== F7 ON-KAYITLI KARAR (8 Eyl'de yazildi) ===")
    for k, ok in v["kosullar"].items():
        print(f"  [{'X' if ok else ' '}] {k}")
    print(f"  iyilesen stratejiler : {v['iyilesen_stratejiler'] or '(yok)'}")
    print(f"  toplam secilen islem : {v['toplam_secilen']}")
    print(f"  KARAR : {v['karar']}")
    print(f"\n  NOT: {v['not']}")
    print("  HATIRLATMA: evren BUGUNKU liste - hayatta kalma yanliligi")
    print("  tum LONG stratejileri yukari yanli (harness ilkesi 6).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
