"""HIPOTEZ 7 RAPORU - golge defter ile ayna ayni sonuca mi vardi?
SALT OKUR: veritabanini read-only acar, hicbir sey yazmaz, servisi
yeniden baslatmaz. 28 Agu kapisinda deploy beklemeden kosulabilsin diye
ayri alet yapildi (seans ici restart yasak - anayasa 2.5).

Kullanim (VM'de, servis calisirken guvenli):
    python3 tools/mirror_disagreement.py
    python3 tools/mirror_disagreement.py --db data/bot.db --json

Hesabi UYDURMAZ: siniflandirma ve oran, servisin kendi kodundan
(app.services.alpaca_mirror.disagreement_report) gelir - iki yerde iki
farkli cevap cikmasin diye.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

# Depo kokunu yola ekle: alet tools/ icinden kosuluyor ama hesabi
# servisin kendi kodundan aliyor (iki yerde iki cevap olmasin).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.alpaca_mirror import disagreement_report  # noqa: E402

SQL = ("SELECT m.alpaca_status, m.closed_reason, s.outcome, s.status, "
       "s.fill_price, s.symbol "
       "FROM mirror_fills m JOIN signals s ON s.id=m.signal_id "
       "WHERE COALESCE(m.closed_reason,'') != 'LATE_ONBOARD'")


def fetch(db_path: str) -> list[dict]:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        con.row_factory = sqlite3.Row
        return [dict(r) for r in con.execute(SQL)]
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/bot.db")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--stdin", action="store_true",
                    help="satirlari JSON olarak stdin'den al (VM'de "
                         "salt-okur sqlite sorgusu kosup ciktisini "
                         "yerel klonda islemek icin - seans ici yol)")
    args = ap.parse_args()
    if args.stdin:
        try:
            rows = json.load(sys.stdin)
        except ValueError as exc:
            print(f"HATA: stdin JSON okunamadi: {exc}")
            return 2
    else:
        try:
            rows = fetch(args.db)
        except sqlite3.Error as exc:
            print(f"HATA: veritabani okunamadi ({args.db}): {exc}")
            return 2
    rep = disagreement_report(rows)
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0
    print("AYNA - karara girmez (hipotez 7 olcusu)")
    print(f"  karsilastirilan cift : {rep['karsilastirilan']}")
    print(f"  henuz sonuclanmamis  : {rep['sonuclanmamis']} (paydaya girmez)")
    print(f"  uyusmayan            : {rep['uyusmaz']}")
    o = rep["uyusmazlik_orani"]
    print(f"  UYUSMAZLIK ORANI     : "
          f"{'olculemedi (cift yok)' if o is None else f'%{o * 100:.1f}'}")
    print(f"  on-kayitli esik      : %25 -> "
          f"{'ASILDI (karar toplantisi)' if rep['esik_asildi'] else 'asilmadi'}")
    y = rep["yon"]
    print("  yon:")
    print(f"    yalniz DEFTER girdi (ayna girmedi): {y['yalniz_defter_girdi']}")
    print(f"    yalniz AYNA girdi (defter girmedi): {y['yalniz_ayna_girdi']}")
    print(f"    kazanc sayisi  defter/ayna        : "
          f"{y['defter_kazanc']}/{y['ayna_kazanc']}")
    if rep["ornekler"]:
        print("  ornek uyusmazliklar (en fazla 12):")
        for e in rep["ornekler"]:
            print(f"    {e['symbol']:<6} defter={e['defter']:<8} "
                  f"ayna={e['ayna']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
