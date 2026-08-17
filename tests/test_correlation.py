"""v4.37: korelasyon olcum aleti (ikiz aktarimi - bybit correlation.py).

Ikiz kurali 3b geregi ANAHTAR TEST: alet salt olcumdur, karar modulleri
import edemez; S1/S5 ayni girisi paylastigi icin korelasyonlari 1.0
cikmali (aletin kendi kendini dogrulamasi). Eski kodda modul olmadigi
icin tum testler kirmizi yanar.
"""
from __future__ import annotations

import ast
from pathlib import Path

from app.services.correlation import (build_report, correlation_matrix,
                                      effective_bets, pearson,
                                      series_from_trades)
from app.services.strategy_lab import Trade

ROOT = Path(__file__).resolve().parents[1]


def _trade(strategy, entry_date, exit_date, r_net, symbol="T"):
    return Trade(strategy=strategy, symbol=symbol, signal_date=entry_date,
                 entry_date=entry_date, entry=100.0, stop=98.0, tp=104.0,
                 exit_price=101.0, exit_date=exit_date, r_net=r_net,
                 outcome="WIN" if r_net > 0 else "LOSS")


def test_pearson_temel():
    assert abs(pearson([1, 2, 3], [2, 4, 6]) - 1.0) < 1e-9
    assert abs(pearson([1, 2, 3], [3, 2, 1]) + 1.0) < 1e-9
    assert pearson([1, 1, 1], [1, 2, 3]) is None     # sifir varyans
    assert pearson([1], [1]) is None                 # n<2


def test_matrix_min_gun_esigi():
    a = {f"2026-08-{d:02d}": float(d % 3) for d in range(1, 12)}   # 11 gun
    b = {f"2026-08-{d:02d}": float(d % 3) for d in range(1, 12)}
    c = {"2026-08-01": 1.0}                                        # 1 gun
    m = correlation_matrix({"A": a, "B": b, "C": c})
    assert m["A|B"]["corr"] is not None
    assert m["A|C"]["corr"] is None                  # esik alti -> olculmez
    assert m["B|C"]["corr"] is None


def test_effective_bets_evren_tutarliligi():
    """Olculemeyen strateji N_eff'i SISIREMEZ (bybit MAJOR bulgusunun
    tasinmis hali): 2 tam-korelasyonlu + 1 olculemeyen -> n_measured=2,
    N_eff ~1 (tek bagimsiz bahis)."""
    a = {f"2026-08-{d:02d}": float(d % 3 - 1) for d in range(1, 15)}
    m = correlation_matrix({"A": a, "B": dict(a), "C": {"2026-08-01": 1.0}})
    eb = effective_bets(m, n=3)
    assert eb["n_measured"] == 2
    assert eb["avg_pairwise_corr"] == 1.0
    assert abs(eb["effective_bets"] - 1.0) < 0.01


def test_ayni_girisli_ciftin_korelasyonu_bir():
    """Kendi kendini dogrulama: S1 ve S5 AYNI girisi paylasir (lab
    tasarimi boyle) - ayni islem kumesiyle korelasyon 1.0 cikmali,
    ortusme orani 1.0 olmali. Cikmiyorsa alet bozuktur."""
    days = [f"2026-08-{d:02d}" for d in range(1, 15)]
    s1 = [_trade("S1", d, d, (i % 3 - 1) * 1.0)
          for i, d in enumerate(days)]
    s5 = [_trade("S5", d, d, (i % 3 - 1) * 1.5)     # ayni gunler, olcekli R
          for i, d in enumerate(days)]
    sx = [_trade("SX", d, d, (1.0 if i in (2, 5) else -0.5))
          for i, d in enumerate(days[:12])]
    rep = build_report({"S1": s1, "S5": s5, "SX": sx})
    assert rep["daily_corr"]["S1|S5"]["corr"] == 1.0
    assert rep["same_day_signal"]["S1|S5"]["rate"] == 1.0
    assert rep["independence"]["n_measured"] == 3
    assert rep["independence"]["effective_bets"] < 3   # tam bagimsiz degiller
    assert rep["basis"] == "net_daily_r"


def test_seriler_islemlerden_dogru_cikar():
    ts = [_trade("S1", "2026-08-01", "2026-08-03", 1.0),
          _trade("S1", "2026-08-02", "2026-08-03", -0.5)]
    series, opens = series_from_trades({"S1": ts})
    assert series["S1"] == {"2026-08-03": 0.5}       # ayni gune toplanir
    assert opens["S1"] == {"2026-08-01", "2026-08-02"}


def test_karar_modulleri_import_edemez():
    """IZOLASYON ANAHTARI (ikiz kural 3b + anayasa 2.4): korelasyon salt
    olcumdur; karar ureten hicbir modul onu import edemez. Ayna
    izolasyonuyla ayni desen - AST duzeyinde olculur."""
    decision_files = list((ROOT / "app" / "strategies").glob("*.py")) + [
        ROOT / "app" / "services" / "signal_tracker.py",
        ROOT / "app" / "scheduler.py",
    ]
    for f in decision_files:
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            assert not any("correlation" in n for n in names), \
                f"{f.name} korelasyon aletini import ediyor - izolasyon ihlali"