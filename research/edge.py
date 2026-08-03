"""
GIRIS SINYALININ HAM DEGERI (cikis mekaniginden bagimsiz).

Ilk kosuda TUM stratejiler negatif cikti. Sebep girisler degil, ortak
cikis mekanigi: stop 1.2 ATR / hedef 1.0 ATR => kazanc 0.83R, kayip
-1R. %53 isabetle bu matematik zaten negatiftir. Yani o test "cikis
tasarimini" olcmus oldu, "girisin ongoru gucunu" degil.

Burada girisi izole ediyoruz: sinyal gunuNUN ERTESI acilisindan
baslayip N gun sonraki kapanisa kadar HAM getiri. Stop yok, hedef yok.
Ve en onemlisi: AYNI GUNUN evren ortalamasi cikarilir (fazla getiri).
Boylece "piyasa yukseldigi icin kazandik" yanilsamasi elenir -
hayatta kalma yanliligi da buyuk olcude notrlesir, cunku hem sinyal
hem kiyas ayni (hayatta kalmis) evrenden gelir.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/claude/bt")
from harness import atr  # noqa: E402
import strategies as S  # noqa: E402

RAW = pd.read_pickle("/home/claude/bt/daily.pkl")
CLOSE, OPEN = RAW["Close"], RAW["Open"]
SYMS = [s for s in open("/tmp/universe.txt").read().split()
        if s in CLOSE.columns and CLOSE[s].notna().sum() > 400]
BENCH = CLOSE["SPY"]
HORIZONS = (5, 10, 20)


def forward_returns(h: int) -> pd.DataFrame:
    """t gunu sinyali -> t+1 acilistan t+h kapanisa getiri."""
    entry = OPEN[SYMS].shift(-1)
    exit_ = CLOSE[SYMS].shift(-h)
    return (exit_ / entry - 1)


def main():
    fwd = {h: forward_returns(h) for h in HORIZONS}
    # evren ortalamasi (ayni gun, ayni ufuk) -> fazla getiri icin
    mkt = {h: fwd[h].mean(axis=1) for h in HORIZONS}
    ranks = (CLOSE[SYMS].shift(21) / CLOSE[SYMS].shift(252) - 1) \
        .rank(axis=1, pct=True)

    sig_map: dict[str, dict[str, pd.DataFrame]] = {}
    for name, fn in S.REGISTRY.items():
        for d in ("LONG", "SHORT"):
            cols = {}
            for sym in SYMS:
                try:
                    bars = pd.DataFrame({
                        "open": RAW["Open"][sym], "high": RAW["High"][sym],
                        "low": RAW["Low"][sym], "close": RAW["Close"][sym],
                        "volume": RAW["Volume"][sym]}).dropna()
                except KeyError:
                    continue
                if len(bars) < 300:
                    continue
                bars["atr"] = atr(bars)
                if name == "2_KESITSEL_MOMENTUM":
                    rp = ranks[sym].reindex(bars.index) if sym in ranks else None
                    s = fn(bars, d, rank_pct=rp)
                elif name == "4_REZIDUEL_STATARB":
                    s = fn(bars, d, bench=BENCH)
                else:
                    s = fn(bars, d)
                if s is not None and s.any():
                    cols[sym] = s.reindex(CLOSE.index).fillna(False)
            if cols:
                sig_map.setdefault(name, {})[d] = pd.DataFrame(cols)

    rows = []
    for name, dirs in sorted(sig_map.items()):
        for d, sig in dirs.items():
            sign = 1 if d == "LONG" else -1
            rec = {"strateji": name, "yon": d, "sinyal": int(sig.values.sum())}
            if rec["sinyal"] < 200:
                continue
            for h in HORIZONS:
                f = fwd[h].reindex(columns=sig.columns)
                m = mkt[h].reindex(f.index)
                excess = (f.sub(m, axis=0)) * sign      # piyasa ustu, yone gore
                vals = excess.where(sig.reindex_like(excess)).values.ravel()
                vals = vals[np.isfinite(vals)]
                if len(vals) < 100:
                    continue
                mean = vals.mean()
                # t-istatistigi: sifirdan anlamli mi (kaba, bagimsizlik varsayar)
                tstat = mean / (vals.std(ddof=1) / np.sqrt(len(vals)))
                rec[f"fazla_{h}g_%"] = round(100 * mean, 3)
                rec[f"t_{h}g"] = round(tstat, 1)
            rows.append(rec)
    out = pd.DataFrame(rows)
    print("=== GIRIS SINYALININ FAZLA GETIRISI (piyasa ustu, %) ===")
    print("t > 2.0 kabaca 'sansa baglamak zor' esigi; isaret onemli\n")
    print(out.to_string(index=False))
    out.to_csv("/home/claude/bt/edge.csv", index=False)


if __name__ == "__main__":
    main()
