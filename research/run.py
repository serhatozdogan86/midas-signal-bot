"""Tum stratejileri tum evrende kosar, sonuclari tabloya doker.

24 Agu (F6): iki degisiklik.
 1) Veri yolu depo icine alindi (research/data.py) - eski
    /home/claude/bt/... yollari gecici bir analiz ortamindaydi ve o
    ortam kapaninca duzenek kosulamaz olmustu.
 2) Hipotez 9 (S6 Squeeze) icin ON-KAYITLI karar kurali KODA yazildi
    (verdict_h9). Kural sonuca bakilmadan once sabitlendigi icin
    "sonuca gore kural esnetme" fiziksel olarak zorlasir.
"""
from __future__ import annotations

import sys

import pandas as pd

from research import strategies as S
from research.data import BENCH, load
from research.harness import ExecConfig, atr, metrics, simulate, verdict_h9

RAW = load()
CLOSE = RAW["Close"]
SYMS = [s for s in CLOSE.columns
        if s != BENCH and CLOSE[s].notna().sum() > 400]
BENCH_PX = CLOSE[BENCH]


def bars_for(sym: str) -> pd.DataFrame | None:
    try:
        df = pd.DataFrame({
            "open": RAW["Open"][sym], "high": RAW["High"][sym],
            "low": RAW["Low"][sym], "close": RAW["Close"][sym],
            "volume": RAW["Volume"][sym]}).dropna()
    except KeyError:
        return None
    if len(df) < 300:
        return None
    df["atr"] = atr(df)
    return df


def momentum_ranks() -> pd.DataFrame:
    """12-1 momentum yuzdeligi (kesitsel, gunluk)."""
    px = CLOSE[SYMS]
    mom = px.shift(21) / px.shift(252) - 1        # son ay HARIC 12 ay
    return mom.rank(axis=1, pct=True)


def run(directions=("LONG", "SHORT"), cfg: ExecConfig | None = None,
        label_suffix: str = "") -> tuple[pd.DataFrame, dict]:
    cfg = cfg or ExecConfig()
    ranks = momentum_ranks()
    all_trades: dict[str, list] = {k: [] for k in S.REGISTRY}
    for sym in SYMS:
        bars = bars_for(sym)
        if bars is None:
            continue
        for name, fn in S.REGISTRY.items():
            for d in directions:
                if name == "2_KESITSEL_MOMENTUM":
                    rp = ranks[sym].reindex(bars.index) if sym in ranks else None
                    sig = fn(bars, d, rank_pct=rp)
                elif name == "4_REZIDUEL_STATARB":
                    sig = fn(bars, d, bench=BENCH_PX)
                else:
                    sig = fn(bars, d)
                if sig is None or not sig.any():
                    continue
                t = simulate(bars, sig, d, cfg)
                if not t.empty:
                    t["symbol"] = sym
                    all_trades[name].append(t)
    frames = {k: (pd.concat(v, ignore_index=True) if v else pd.DataFrame())
              for k, v in all_trades.items()}
    rows = [metrics(t, k + label_suffix) for k, t in sorted(frames.items())]
    return pd.DataFrame(rows), frames


if __name__ == "__main__":
    print(f"evren: {len(SYMS)} sembol (kiyas: {BENCH})\n")
    tbl, frames = run()
    print("=== TUM DONEM, LONG+SHORT, ortak cikis mekanigi ===")
    print(tbl.to_string(index=False))
    print("\nHATIRLATMA: evren BUGUNKU liste - hayatta kalma yanliligi")
    print("tum LONG stratejileri yukari yanli (harness ilkesi 6).\n")
    v = verdict_h9(frames)
    print("=== HIPOTEZ 9 (S6 Squeeze) ON-KAYITLI KARAR ===")
    for k, ok in v.get("kosullar", {}).items():
        print(f"  [{'X' if ok else ' '}] {k}")
    if "olcum" in v:
        print(f"  olcum : {v['olcum']}")
        print(f"  yari-1: {v['ilk_yari']}")
        print(f"  yari-2: {v['ikinci_yari']}")
        print(f"  rakip beklentiler: {v['rakip_beklenti']}")
    print(f"  KARAR : {v['karar']}")
    out = "research/_data/trades.pkl"
    pd.to_pickle(frames, out)
    print(f"\nislem defterleri: {out}")
    sys.exit(0)
