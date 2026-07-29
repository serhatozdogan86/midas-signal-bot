"""
Market report - gunluk ABD piyasa notu (SAF FONKSIYONLAR, I/O yok).

Kripto botundaki market_info panelinin ABD uyarlamasi; dis kaynak (haber RSS,
ek API) YOKTUR - elimizdeki gunluk mumlardan turetilir:
- SPY / QQQ son gun degisimi + rejim
- Genislik: evrende SMA50 uzerindeki hisse orani (katilim olcusu)
- RS liderleri / zayiflari (63g, SPY'a gore) - long/short aday havuzu sinyali
- Bilanco blackout'taki sembol sayisi (bugun evrenin ne kadari devre disi)

Cikti hazirlik (15:45 TR) Telegram mesajina, dashboard'a ve /diag'a gider.
"""
from __future__ import annotations

import pandas as pd

from app.models.candle import KlineSeries
from app.strategies.indicators import sma
from app.strategies.relative_strength import rs_score


def _last_change_pct(df: pd.DataFrame) -> float | None:
    if df is None or len(df) < 2:
        return None
    prev, last = float(df["close"].iloc[-2]), float(df["close"].iloc[-1])
    return round((last / prev - 1) * 100, 2) if prev else None


def build_market_snapshot(daily: dict[str, KlineSeries],
                          universe_symbols: list[str],
                          regime: str,
                          spy_symbol: str = "SPY",
                          qqq_symbol: str = "QQQ",
                          earnings_blackout_count: int = 0,
                          rs_lookback: int = 63,
                          top_n: int = 5) -> dict:
    spy_df = (daily[spy_symbol].to_dataframe()
              if spy_symbol in daily else None)
    qqq_df = (daily[qqq_symbol].to_dataframe()
              if qqq_symbol in daily else None)

    above = total = 0
    rs_rows: list[tuple[str, float]] = []
    for symbol in universe_symbols:
        series = daily.get(symbol)
        if series is None:
            continue
        df = series.to_dataframe()
        if len(df) < 60:
            continue
        total += 1
        ma50 = sma(df["close"], 50)
        if float(df["close"].iloc[-1]) > float(ma50.iloc[-1]):
            above += 1
        if spy_df is not None and len(df) > rs_lookback:
            score = rs_score(df["close"], spy_df["close"], rs_lookback)
            if score is not None:
                rs_rows.append((symbol, score))

    rs_rows.sort(key=lambda x: x[1], reverse=True)
    return {
        "regime": regime,
        "spy_change_pct": _last_change_pct(spy_df),
        "qqq_change_pct": _last_change_pct(qqq_df),
        "breadth_above_50ma_pct": (round(100 * above / total, 1)
                                   if total else None),
        "breadth_sample": total,
        "rs_leaders": [{"symbol": s, "rs": round(r, 1)}
                       for s, r in rs_rows[:top_n]],
        "rs_laggards": [{"symbol": s, "rs": round(r, 1)}
                        for s, r in rs_rows[-top_n:]][::-1] if rs_rows else [],
        "earnings_blackout_count": earnings_blackout_count,
    }


def _pct(v: float | None) -> str:
    return f"{v:+.2f}%" if v is not None else "-"


def render_market_note(snap: dict) -> str:
    """Hazirlik mesaji / dashboard icin kisa gunluk piyasa notu (ASCII)."""
    lines = [f"Gunluk piyasa notu ({snap.get('regime', '-')} rejimi)"]
    lines.append(f"SPY {_pct(snap.get('spy_change_pct'))} | "
                 f"QQQ {_pct(snap.get('qqq_change_pct'))} (onceki gun)")

    breadth = snap.get("breadth_above_50ma_pct")
    if breadth is not None:
        if breadth >= 60:
            b_txt = "genis katilim - trend saglikli"
        elif breadth >= 40:
            b_txt = "karisik katilim - secici olunmali"
        else:
            b_txt = "dar katilim - yukselisler kirilgan, long'da temkin"
        lines.append(f"Genislik: evrenin %{breadth:.0f}'i 50G MA uzerinde "
                     f"({b_txt})")

    leaders = snap.get("rs_leaders") or []
    if leaders:
        lines.append("RS liderleri: " + ", ".join(
            f"{r['symbol']} ({r['rs']:+.0f}pp)" for r in leaders))
    laggards = snap.get("rs_laggards") or []
    if laggards:
        lines.append("RS zayiflari: " + ", ".join(
            f"{r['symbol']} ({r['rs']:+.0f}pp)" for r in laggards))

    eb = snap.get("earnings_blackout_count") or 0
    if eb:
        lines.append(f"Bilanco blackout: {eb} sembol bugun devre disi "
                     "(+-2 gun kurali)")
    regime = snap.get("regime")
    if regime == "BULL":
        lines.append("Plan: yalniz LONG taranir; geri cekilme alimlari oncelikli.")
    elif regime == "BEAR":
        lines.append("Plan: yalniz SHORT taranir (siki esikler); "
                     "tepki yukselislerinde zayif RS aranir.")
    elif regime == "NEUTRAL":
        lines.append("Plan: iki yon acik ama esikler sikilastirildi "
                     "(min RR +0.5, hacim esigi +0.2).")
    else:
        lines.append("Plan: rejim belirsiz -> sinyal uretilmez, veri beklenir.")
    return "\n".join(lines)
