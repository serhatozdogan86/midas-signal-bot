"""Tum stratejileri tum evrende kosar, sonuclari tabloya doker."""
from __future__ import annotations

import sys

import pandas as pd

sys.path.insert(0, "/home/claude/bt")
from harness import ExecConfig, atr, by_period, metrics, simulate  # noqa: E402
import strategies as S  # noqa: E402

RAW = pd.read_pickle("/home/claude/bt/daily.pkl")
CLOSE = RAW["Close"]
SYMS = [s for s in open("/tmp/universe.txt").read().split()
        if s in CLOSE.columns and CLOSE[s].notna().sum() > 400]
BENCH = CLOSE["SPY"]


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
    for i, sym in enumerate(SYMS):
        bars = bars_for(sym)
        if bars is None:
            continue
        for name, fn in S.REGISTRY.items():
            for d in directions:
                if name == "2_KESITSEL_MOMENTUM":
                    rp = ranks[sym].reindex(bars.index) if sym in ranks else None
                    sig = fn(bars, d, rank_pct=rp)
                elif name == "4_REZIDUEL_STATARB":
                    sig = fn(bars, d, bench=BENCH)
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
    print(f"evren: {len(SYMS)} sembol\n")
    tbl, frames = run()
    print("=== TUM DONEM (2021-2026), LONG+SHORT, ortak cikis mekanigi ===")
    print(tbl.to_string(index=False))
    pd.to_pickle(frames, "/home/claude/bt/trades.pkl")
