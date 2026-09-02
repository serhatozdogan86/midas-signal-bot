"""ZARAR ANATOMISI RAPORU (Faz 4 / F1) - salt-okur CLI.

"Bu kurulum neden kaybediyor?" sorusunun dort alt sorusunu KAPALI
kohorttan olcer. Veritabanini read-only acar, hicbir sey yazmaz,
servisi yeniden baslatmaz - seans ici de kosulabilir.

Kullanim:
    python3 tools/loss_anatomy.py
    python3 tools/loss_anatomy.py --db data/bot.db --json
    python3 tools/loss_anatomy.py --blocked        # engelli kohortu da al

Hesabi kendi yapmaz: app/services/loss_anatomy.py'yi cagirir; karar
kurallari orada, SONUCA BAKILMADAN yazildi.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.loss_anatomy import (breakdown, excursions,   # noqa: E402
                                       q1_entry_or_exit, q2_setup_flags,
                                       q3_short_verdict)

SIG_SQL = (
    "SELECT id, symbol, direction, outcome, r_multiple, fill_price, fill_ts, "
    "stop_loss, entry_min, entry_max, closed_utc, setup_type, confidence, "
    "contract_json, blocked "
    "FROM signals WHERE status='CLOSED' AND blocked{blocked_filter}")

CANDLE_SQL = ("SELECT high, low FROM candles WHERE symbol=? AND interval='1h' "
              "AND ts>=? AND ts<=? ORDER BY ts ASC")


def _epoch_ms(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        s = iso.replace("Z", "+00:00")
        return int(datetime.fromisoformat(s)
                   .replace(tzinfo=timezone.utc).timestamp() * 1000)
    except ValueError:
        return None


def collect(db_path: str, include_blocked: bool = False) -> list[dict]:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        con.row_factory = sqlite3.Row
        sql = SIG_SQL.format(blocked_filter=">=0" if include_blocked else "=0")
        rows = [dict(r) for r in con.execute(sql)]
        for r in rows:
            r["r"] = r.pop("r_multiple", None)
            cj = r.pop("contract_json", None)
            try:
                c = json.loads(cj) if cj else {}
            except ValueError:
                c = {}
            r["market_regime"] = c.get("market_regime")
            r["session_phase"] = c.get("session_phase")
            r["trend_bias"] = c.get("trend_bias")
            # MFE/MAE yalniz DOLAN ve kapanan kayitlarda olculebilir
            bas, son = r.get("fill_ts"), _epoch_ms(r.get("closed_utc"))
            highs: list[float] = []
            lows: list[float] = []
            if bas and son and son >= bas:
                for c2 in con.execute(CANDLE_SQL, (r["symbol"], bas, son)):
                    if c2["high"] is not None and c2["low"] is not None:
                        highs.append(c2["high"])
                        lows.append(c2["low"])
            r["mum_sayisi"] = len(highs)
            r["mfe"], r["mae"] = excursions(r["direction"], r.get("fill_price"),
                                            r.get("stop_loss"), highs, lows)
        return rows
    finally:
        con.close()


def _tablo(baslik: str, satirlar: list[dict]) -> None:
    print(f"\n  {baslik}")
    print(f"    {'grup':<18}{'n':>4}{'net R':>9}{'kazanma %':>11}")
    for g in satirlar:
        kz = "-" if g["kazanma_%"] is None else f"{g['kazanma_%']:.1f}"
        print(f"    {str(g['grup'])[:18]:<18}{g['n']:>4}{g['net_r']:>9.2f}"
              f"{kz:>11}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/bot.db")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--blocked", action="store_true",
                    help="engelli kohortlari da dahil et (varsayilan: yalniz "
                         "karneye giren blocked=0 kayitlar)")
    args = ap.parse_args()
    try:
        rows = collect(args.db, args.blocked)
    except sqlite3.Error as exc:
        print(f"HATA: veritabani okunamadi ({args.db}): {exc}")
        return 2

    dolan = [r for r in rows if r.get("fill_price") is not None]
    zarar = [r for r in dolan if r.get("outcome") == "LOSS"]
    kazanc = [r for r in dolan if r.get("outcome") == "WIN"]
    q1 = q1_entry_or_exit(zarar)
    q2 = q2_setup_flags(dolan)
    q3 = q3_short_verdict(dolan)

    if args.json:
        print(json.dumps({"q1": q1, "q2_bayrakli_setuplar": q2, "q3_short": q3,
                          "setup": breakdown(dolan, "setup_type"),
                          "rejim": breakdown(dolan, "market_regime"),
                          "faz": breakdown(dolan, "session_phase"),
                          "yon": breakdown(dolan, "direction"),
                          "kayitlar": rows}, ensure_ascii=False, indent=2))
        return 0

    print("ZARAR ANATOMISI (Faz 4 / F1) - salt olcum")
    print(f"  kapanan kayit: {len(rows)} | dolan: {len(dolan)} | "
          f"kazanc: {len(kazanc)} | zarar: {len(zarar)}")

    print("\n  Q1 - GIRIS MI CIKIS MI? (zararlarin MFE medyani)")
    print(f"    olculen zarar    : {q1['n']}")
    print(f"    medyan MFE       : {q1['medyan_mfe']} R")
    print(f"    ON-KAYITLI HUKUM : {q1['hukum']}")
    if "dayaniklilik" in q1:
        d = q1["dayaniklilik"]
        print(f"    DAYANIKLILIK     : "
              f"{'saglam' if d['saglam'] else 'ZAYIF'} - {d['not']}")
    if zarar:
        print("    (MFE dagilimi, en iyiden kotuye)")
        for r in sorted(zarar, key=lambda x: -(x["mfe"] or -99))[:15]:
            print(f"      {r['symbol']:<6} MFE={r['mfe']}  MAE={r['mae']}  "
                  f"R={r['r']}  mum={r['mum_sayisi']}")

    _tablo("Q2 - SETUP KIRILIMI", breakdown(dolan, "setup_type"))
    if q2:
        print(f"    BAYRAK: {[g['grup'] for g in q2]} -> KILIT-3 incelemesine")
    else:
        print("    bayrak yok (n>=5 VE net-R<=-3.0 sarti saglayan setup)")

    print(f"\n  Q3 - SHORT TARAFI: n={q3['n']}, net {q3['net_r']}R")
    print(f"    ON-KAYITLI HUKUM : {q3['hukum']}")

    _tablo("Q4 - REJIM (yalniz rapor, karar kurali YOK)",
           breakdown(dolan, "market_regime"))
    _tablo("Q4 - SEANS FAZI (yalniz rapor)", breakdown(dolan, "session_phase"))
    _tablo("YON", breakdown(dolan, "direction"))
    print("\n  NOT: dolmayan (NOT_FILLED) kayitlar bu tablolarda yok - "
          "onlarin sorusu F4b.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
