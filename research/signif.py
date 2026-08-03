"""
ANLAMLILIK - DURUSTCE.

edge.py'deki t degerleri SISKIN: her gozlemi bagimsiz sayiyor. Oysa
ayni gun 40 sembol sinyal verdiginde bunlar ayni piyasa hareketini
paylasir (kesitsel korelasyon), ustelik ust uste binen ufuklar
(overlapping windows) ardisik bagimlilik yaratir. Bu iki etki t'yi
kolayca 3-4 kat abartir.

Duzeltme: once GUNLUK PORTFOY getirisi (o gun sinyal veren sembollerin
esit agirlikli ortalamasi, piyasa ustu), sonra bu ZAMAN SERISI uzerinde
Newey-West (lag = ufuk) duzeltmeli t. Boylece hem kesitsel korelasyon
hem ust uste binme hesaba katilir.
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
HORIZONS = (5, 20)


def nw_tstat(x: pd.Series, lag: int) -> tuple[float, float]:
    """Newey-West duzeltmeli ortalama ve t."""
    x = x.dropna()
    n = len(x)
    if n < 30:
        return np.nan, np.nan
    mu = x.mean()
    e = (x - mu).values
    gamma0 = (e @ e) / n
    var = gamma0
    for L in range(1, min(lag, n - 1) + 1):
        w = 1 - L / (lag + 1)
        cov = (e[L:] @ e[:-L]) / n
        var += 2 * w * cov
    se = np.sqrt(max(var, 1e-18) / n)
    return mu, mu / se


def build_signals():
    ranks = (CLOSE[SYMS].shift(21) / CLOSE[SYMS].shift(252) - 1) \
        .rank(axis=1, pct=True)
    out = {}
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
                out[(name, d)] = pd.DataFrame(cols)
    return out


def main():
    sigs = build_signals()
    rows = []
    for h in HORIZONS:
        entry = OPEN[SYMS].shift(-1)
        fwd = CLOSE[SYMS].shift(-h) / entry - 1
        mkt = fwd.mean(axis=1)
        for (name, d), sig in sorted(sigs.items()):
            sign = 1 if d == "LONG" else -1
            f = fwd.reindex(columns=sig.columns)
            ex = f.sub(mkt, axis=0) * sign
            daily = ex.where(sig.reindex_like(ex)).mean(axis=1)  # gunluk portfoy
            gunler = int(daily.notna().sum())
            if gunler < 60:
                continue
            mu, t = nw_tstat(daily, lag=h)
            # donem kararliligi: ilk yari / ikinci yari
            half = daily.dropna().index[len(daily.dropna()) // 2]
            mu1, _ = nw_tstat(daily[daily.index < half], lag=h)
            mu2, _ = nw_tstat(daily[daily.index >= half], lag=h)
            rows.append({
                "strateji": name, "yon": d, "ufuk_g": h, "sinyal_gunu": gunler,
                "fazla_%": round(100 * mu, 3), "t_NW": round(t, 2),
                "ilk_yari_%": round(100 * mu1, 3),
                "ikinci_yari_%": round(100 * mu2, 3),
                "kararli": "EVET" if (mu1 > 0) == (mu2 > 0) and abs(t) > 2
                           else "hayir"})
    out = pd.DataFrame(rows).sort_values(["ufuk_g", "t_NW"], ascending=[True, False])
    print("=== NEWEY-WEST DUZELTMELI (gunluk portfoy bazinda) ===")
    print("t_NW > 2 anlamli sayilir; 'kararli' = iki alt donemde ayni isaret\n")
    for h in HORIZONS:
        print(f"--- {h} islem gunu ---")
        print(out[out.ufuk_g == h].to_string(index=False))
        print()
    out.to_csv("/home/claude/bt/signif.csv", index=False)


if __name__ == "__main__":
    main()
