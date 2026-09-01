"""AYNA UYUSMAZLIK ANATOMISI (salt-okur CLI) - karar toplantisi B adimi.

Her uyusmazlik cifti icin fiyatin giris bolgesine NE KADAR girdigini
olcer (nufuz orani) ve yon hukmunu on-kayitli kurala gore verir.
Hesabi kendi yapmaz: app/services/mirror_anatomy.py'yi cagirir.

Kullanim (VM'de, servis calisirken guvenli - hicbir sey yazmaz):
    python3 tools/mirror_pair_anatomy.py
    python3 tools/mirror_pair_anatomy.py --db data/bot.db --json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config.settings import Settings                      # noqa: E402
from app.services.mirror_anatomy import (anatomy_rows,        # noqa: E402
                                         anatomy_summary)

PAIR_SQL = (
    "SELECT s.id, s.symbol, s.direction, s.entry_min, s.entry_max, "
    "s.stop_loss, s.fill_price, s.status, s.outcome, s.entry_candle_ts, "
    "m.alpaca_status, m.closed_reason, m.alpaca_fill_price "
    "FROM mirror_fills m JOIN signals s ON s.id=m.signal_id "
    "WHERE COALESCE(m.closed_reason,'') != 'LATE_ONBOARD'")

# Dolum penceresi defterle BIREBIR ayni mum listesi (1h, dogum barindan
# sonraki FILL_WINDOW_BARS mum) - baska pencere secmek olcumu bozar.
WINDOW_SQL = (
    "SELECT MIN(low) lo, MAX(high) hi, COUNT(*) n FROM ("
    "  SELECT low, high FROM candles WHERE symbol=? AND interval=? "
    "  AND ts>? ORDER BY ts ASC LIMIT ?)")


def collect(db_path: str) -> list[dict]:
    s = Settings()
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        con.row_factory = sqlite3.Row
        rows = [dict(r) for r in con.execute(PAIR_SQL)]
        for r in rows:
            w = con.execute(WINDOW_SQL, (r["symbol"], "1h",
                                         r["entry_candle_ts"] or 0,
                                         s.FILL_WINDOW_BARS)).fetchone()
            r["lowest"] = w["lo"] if w else None
            r["highest"] = w["hi"] if w else None
            r["bar_sayisi"] = w["n"] if w else 0
        return rows
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/bot.db")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    try:
        pairs = collect(args.db)
    except sqlite3.Error as exc:
        print(f"HATA: veritabani okunamadi ({args.db}): {exc}")
        return 2
    rows = anatomy_rows(pairs)
    ozet = anatomy_summary(rows)
    if args.json:
        print(json.dumps({"satirlar": rows, "ozet": ozet},
                         ensure_ascii=False, indent=2))
        return 0
    print("AYNA - karara girmez (uyusmazlik anatomisi)")
    print(f"  uyusmazlik sayisi: {len(rows)}\n")
    print(f"  {'sembol':<7}{'yon':<6}{'defter':<9}{'ayna':<9}"
          f"{'nufuz':>7}  {'mum':>4}  bolge")
    for r in rows:
        nf = "veri yok" if r["nufuz"] is None else f"{r['nufuz']:.2f}"
        print(f"  {str(r['symbol']):<7}{str(r['direction']):<6}"
              f"{r['defter']:<9}{r['ayna']:<9}{nf:>7}  "
              f"{r['bar_sayisi']:>4}  "
              f"{r['entry_min']}-{r['entry_max']}")
    print("\n  nufuz: 1.00 = bolgeyi TAM katetti (defterin dolum sarti)")
    print("         0.00 = bolgenin yakin ucuna bile gelmedi")
    print(f"\n  defterin KACIRDIGI vaka : {ozet['kacirilan_vaka']}")
    print(f"  medyan nufuz            : {ozet['medyan_nufuz']}")
    print(f"  cikis ayrismasi (ayri)  : {ozet['cikis_ayrismasi']}")
    print(f"  ON-KAYITLI YORUM        : {ozet['hukum']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
