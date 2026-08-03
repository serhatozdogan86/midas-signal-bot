"""
STRATEJI KARSILASTIRMA DUZENEGI (backtest harness)

Tasarim ilkesi: SINYAL katmani ile YURUTME katmani ayrilir.
- Sinyal katmani  = her stratejinin kendi kurali (ne zaman, hangi yon)
- Yurutme katmani = TUM stratejiler icin AYNI (giris, stop, hedef,
  time-stop, maliyet). Boylece fark "girisin degeri"nden gelir; cikis
  mekanigi farki sonucu kirletmez.

Onyargi kontrolleri (hepsi bilincli):
1) LOOK-AHEAD YOK: sinyal t gununun KAPANISIYLA hesaplanir, giris t+1
   ACILISINDAN yapilir. Stop/hedef t+1..t+N mumlarinda aranir.
2) KOTUMSER GUN ICI SIRA: bir gunde hem stop hem hedef vurulduysa STOP
   sayilir (hangisinin once geldigini gunluk mumdan bilemeyiz).
3) GAP: acilis stop'un otesindeyse cikis ACILIS fiyatindan (stop'tan
   degil) - gercek zarar budur.
4) MALIYET: Midas modeli - 2 x 1.50$ sabit + 5bp iki yonlu kayma,
   10.000$ referans buyuklukte => %0.08 gidis-donus. R'ye cevrilir.
5) PARAMETRE UYDURMA YOK: her strateji LITERATURDEKI kanonik
   parametreleriyle kosar. Optimize etmiyoruz - optimize edersek
   "hangisi gecmise daha iyi uyduruldu" olcmus oluruz.
6) HAYATTA KALMA YANLILIGI: evren BUGUNKU Midas listesi. Batmis/
   listeden dusmus sirketler yok => TUM long stratejileri yukari
   yanli. Karsilastirma icin kabul edilebilir (herkese ayni etki),
   mutlak getiri icin DEGIL. Raporda tekrar hatirlatilir.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# --- Midas maliyet modeli ---
FEE_USD = 1.50 * 2          # gidis-donus sabit ucret
REF_NOTIONAL = 10_000.0     # referans pozisyon buyuklugu
SLIPPAGE_PCT = 0.0005       # 5bp iki yonlu
COST_PCT = FEE_USD / REF_NOTIONAL + SLIPPAGE_PCT   # %0.08


@dataclass
class ExecConfig:
    atr_stop: float = 1.2       # stop = giris -+ 1.2 x ATR14
    atr_tp: float = 1.0         # hedef = giris -+ 1.0 x ATR14 (TP1'de tam cikis)
    max_hold: int = 4           # time-stop (islem gunu)
    use_target: bool = True     # False ise yalniz stop + time-stop


def atr(h: pd.DataFrame, n: int = 14) -> pd.Series:
    tr = pd.concat([h["high"] - h["low"],
                    (h["high"] - h["close"].shift()).abs(),
                    (h["low"] - h["close"].shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def simulate(bars: pd.DataFrame, signals: pd.Series, direction: str,
             cfg: ExecConfig) -> pd.DataFrame:
    """signals: True olan gunlerde ERTESI GUN acilistan giris.
    bars: open/high/low/close/volume + 'atr' kolonlari, tarih indeksli."""
    out = []
    idx = bars.index
    a = bars["atr"].values
    o, h, low, c = (bars[k].values for k in ("open", "high", "low", "close"))
    sig = signals.reindex(idx).fillna(False).values
    n = len(idx)
    long = direction == "LONG"
    for i in range(n - 1):
        if not sig[i] or np.isnan(a[i]) or a[i] <= 0:
            continue
        entry = o[i + 1]
        if not np.isfinite(entry) or entry <= 0:
            continue
        risk = cfg.atr_stop * a[i]
        stop = entry - risk if long else entry + risk
        tp = entry + cfg.atr_tp * a[i] if long else entry - cfg.atr_tp * a[i]
        exit_px, exit_i, reason = None, None, None
        for j in range(i + 1, min(i + 1 + cfg.max_hold, n)):
            if long:
                if o[j] <= stop:                       # gap ile stop otesi acilis
                    exit_px, reason = o[j], "GAP_STOP"
                elif low[j] <= stop:                   # kotumser: stop once
                    exit_px, reason = stop, "STOP"
                elif cfg.use_target and h[j] >= tp:
                    exit_px, reason = tp, "TP"
            else:
                if o[j] >= stop:
                    exit_px, reason = o[j], "GAP_STOP"
                elif h[j] >= stop:
                    exit_px, reason = stop, "STOP"
                elif cfg.use_target and low[j] <= tp:
                    exit_px, reason = tp, "TP"
            if exit_px is not None:
                exit_i = j
                break
        if exit_px is None:                            # time-stop
            j = min(i + cfg.max_hold, n - 1)
            exit_px, exit_i, reason = c[j], j, "TIME"
        gross = (exit_px - entry) if long else (entry - exit_px)
        r_gross = gross / risk
        cost_r = (COST_PCT * entry) / risk             # maliyetin R karsiligi
        out.append({"entry_date": idx[i + 1], "exit_date": idx[exit_i],
                    "entry": entry, "stop": stop, "exit": exit_px,
                    "r_gross": r_gross, "r_net": r_gross - cost_r,
                    "reason": reason, "direction": direction,
                    "bars_held": exit_i - i})
    return pd.DataFrame(out)


def metrics(trades: pd.DataFrame, label: str) -> dict:
    if trades.empty:
        return {"strateji": label, "islem": 0}
    t = trades.sort_values("exit_date")
    r = t["r_net"]
    eq = r.cumsum()
    dd = (eq.cummax() - eq).max()
    wins = (r > 0).sum()
    return {
        "strateji": label,
        "islem": len(t),
        "isabet_%": round(100 * wins / len(t), 1),
        "beklenti_R": round(r.mean(), 3),
        "toplam_R": round(r.sum(), 1),
        "maxDD_R": round(dd, 1),
        "ort_kazanc": round(r[r > 0].mean(), 2) if wins else 0.0,
        "ort_kayip": round(r[r <= 0].mean(), 2) if wins < len(t) else 0.0,
        "ort_gun": round(t["bars_held"].mean(), 1),
    }


def by_period(trades: pd.DataFrame, label: str) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    t = trades.copy()
    t["yil"] = pd.to_datetime(t["exit_date"]).dt.year
    rows = []
    for y, g in t.groupby("yil"):
        m = metrics(g, f"{label} {y}")
        rows.append(m)
    return pd.DataFrame(rows)
