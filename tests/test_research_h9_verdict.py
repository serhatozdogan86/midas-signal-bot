"""Hipotez 9 (S6 Squeeze) ON-KAYITLI karar kuralinin testleri.

Neden burasi test ediliyor: backtest SONUCU test edilemez (veri
degisir), ama KARAR KURALI edilebilir - ve tehlike zaten sonucta
degil kuralda. "Sonuca bakip esik esnetme" bu deponun en pahali
hatasi olurdu; kural kodda ve testte sabitse esnetmek gorunur olur.

Kural (research-log.md sat. 44): >=100 islem VE net beklenti > 0 VE
iki yari tutarli VE S1-S5 arasinda ilk 3 -> S6 strategy_lab'e; biri
bile saglanmazsa RED.
"""
from __future__ import annotations

import pandas as pd

from research.harness import verdict_h9

# S1-S5 rakipleri: beklentileri sirasiyla 0.20 / 0.10 / 0.05 / 0.02 /
# -0.10 olacak sekilde kurulur (ilk-3 esigi boylece 0.05'tir).
_RAKIP_BEKLENTI = {"1_A": 0.20, "2_B": 0.10, "3_C": 0.05,
                   "4_D": 0.02, "5_E": -0.10}


def _frame(n: int, r: float, ikinci_yari_r: float | None = None):
    """n islemlik sahte defter; r = ortalama net R (maliyet dahil kabul).
    ikinci_yari_r verilirse donem ikiye bolunup isaret farklilastirilir."""
    rows = []
    for i in range(n):
        val = r
        if ikinci_yari_r is not None and i >= n // 2:
            val = ikinci_yari_r
        rows.append({"exit_date": pd.Timestamp("2025-01-01")
                     + pd.Timedelta(days=i), "r_net": val,
                     "bars_held": 3})
    return pd.DataFrame(rows)


def _frames(s6: pd.DataFrame) -> dict:
    f = {k: _frame(120, v) for k, v in _RAKIP_BEKLENTI.items()}
    f["6_SQUEEZE_KIRILIM"] = s6
    return f


def test_dort_kosul_saglaninca_gecer():
    v = verdict_h9(_frames(_frame(120, 0.12)))
    assert v["karar"] == "S6 -> strategy_lab"
    assert all(v["kosullar"].values())


def test_orneklem_kucukse_red():
    """99 islem: beklenti harika olsa bile GECMEZ (n esigi baglayici)."""
    v = verdict_h9(_frames(_frame(99, 0.50)))
    assert v["karar"] == "RED"
    assert v["kosullar"]["islem >= 100"] is False
    assert v["kosullar"]["net beklenti > 0"] is True


def test_negatif_beklenti_red():
    v = verdict_h9(_frames(_frame(150, -0.03)))
    assert v["karar"] == "RED"
    assert v["kosullar"]["net beklenti > 0"] is False


def test_yarilar_tutarsizsa_red():
    """Toplam pozitif ama kazanc TEK yaridan geliyor: RED.
    (Ilk yari +0.40, ikinci yari -0.10 -> ortalama +0.15 > 0)"""
    s6 = _frame(200, 0.40, ikinci_yari_r=-0.10)
    v = verdict_h9(_frames(s6))
    assert v["kosullar"]["net beklenti > 0"] is True
    assert v["kosullar"]["iki yari tutarli"] is False
    assert v["karar"] == "RED"


def test_rakiplerin_gerisindeyse_red():
    """Pozitif + tutarli + bol islem ama S1-S5 icinde 4. sirada
    (0.03 < 0.05): on-kayit 'ilk 3' dedi, RED."""
    v = verdict_h9(_frames(_frame(300, 0.03)))
    assert v["kosullar"]["net beklenti > 0"] is True
    assert v["kosullar"]["S1-S5 icinde ilk 3 (beklenti)"] is False
    assert v["karar"] == "RED"


def test_hic_islem_yoksa_red():
    v = verdict_h9(_frames(pd.DataFrame()))
    assert v["karar"] == "RED"
    assert "islem" in v["gerekce"]
