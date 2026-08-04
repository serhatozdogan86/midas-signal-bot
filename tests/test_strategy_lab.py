"""v3.21 strateji laboratuvari - KATMAN 2 (farkli girisler, ayni cikis)."""
from __future__ import annotations

from app.services.strategy_lab import (COST_PCT, MAX_HOLD, Trade, apply_caps,
                                       atr, momentum_12_1, rsi_wilder,
                                       signals_donchian, signals_rsi2,
                                       signals_vol_break, simulate_symbol,
                                       summarize)


def _bars(seq, vol=1e6, start="2026-01-01"):
    """seq: (open, high, low, close) dortlulerinden liste."""
    from datetime import date, timedelta
    d0 = date.fromisoformat(start)
    out = []
    for i, (o, h, low, c) in enumerate(seq):
        out.append({"date": (d0 + timedelta(days=i)).isoformat(),
                    "open": o, "high": h, "low": low, "close": c,
                    "volume": vol})
    return out


def _flat(n, px=100.0, vol=1e6):
    return _bars([(px, px + 1, px - 1, px)] * n, vol=vol)


# ------------------------------------------------------- gostergeler
def test_atr_is_none_until_window_filled():
    a = atr(_flat(20))
    assert a[12] is None and a[13] is not None
    assert round(a[15], 3) == 2.0            # duz seride TR = 2


def test_rsi2_extremes():
    up = rsi_wilder([100 + i for i in range(30)], 2)
    dn = rsi_wilder([100 - i for i in range(30)], 2)
    assert up[-1] > 95 and dn[-1] < 5


def test_momentum_needs_full_year():
    bars = _flat(300)
    assert momentum_12_1(bars, 100) is None      # 252 bar dolmadan yok
    assert momentum_12_1(bars, 260) == 0.0       # duz seri -> %0


# ------------------------------------------------- sinyal ureticiler
def test_donchian_fires_only_above_prior_high():
    bars = _flat(25) + _bars([(100, 108, 99, 107)])   # kirilim
    sig = signals_donchian(bars)
    assert sig[-1] is True
    assert not any(sig[:-1])


def test_vol_breakout_requires_volume_confirmation():
    base = _flat(25)
    weak = base + _bars([(100, 108, 99, 107)], vol=1e6)      # hacim ort. = 1e6
    strong = base + _bars([(100, 108, 99, 107)], vol=2.5e6)
    assert signals_vol_break(weak)[-1] is False
    assert signals_vol_break(strong)[-1] is True


def test_rsi2_requires_trend_filter():
    # 200G MA ALTINDA sert dusus -> RSI(2) dusuk ama sinyal YOK
    down = _bars([(100 - i, 101 - i, 99 - i, 100 - i) for i in range(220)])
    assert not any(signals_rsi2(down))


# ---------------------------------------------------------- yurutme
def test_entry_is_next_open_no_lookahead():
    bars = _flat(20) + _bars([(100, 101, 99, 100), (105, 106, 104, 105)])
    sig = [False] * (len(bars) - 2) + [True, False]
    tr = simulate_symbol("X", bars, sig, "T")
    assert len(tr) == 1 and tr[0].entry == 105.0        # ERTESI acilis


def test_stop_wins_when_both_hit_same_day():
    """Kotumser gun ici sira: ayni gun stop ve hedef -> STOP."""
    bars = _flat(20) + _bars([(100, 101, 99, 100),
                              (100, 120, 80, 100)])    # her ikisi de vurulur
    sig = [False] * (len(bars) - 2) + [True, False]
    tr = simulate_symbol("X", bars, sig, "T")[0]
    assert tr.outcome == "LOSS" and tr.r_net < 0


def test_gap_below_stop_exits_at_open_not_stop():
    # sinyal t'de; giris t+1 acilisi (100); t+2 STOP'un ALTINDA acilir.
    # (Ilk kurgumda bosluk barini GIRIS bari yapmistim - gap olusmuyordu.)
    bars = _flat(20) + _bars([(100, 101, 99, 100),      # sinyal bari
                              (100, 101, 99, 100),      # giris bari
                              (90, 91, 89, 90)])        # gap ile acilis
    sig = [False] * (len(bars) - 3) + [True, False, False]
    tr = simulate_symbol("X", bars, sig, "T")[0]
    assert tr.entry == 100.0
    assert tr.exit_price == 90.0                       # acilistan
    assert tr.r_net < -1.0                             # 1R'den DERIN kayip


def test_time_stop_closes_position():
    bars = _flat(30)
    sig = [False] * 20 + [True] + [False] * 9
    tr = simulate_symbol("X", bars, sig, "T")[0]
    assert tr.outcome == "EXPIRED"
    idx = [b["date"] for b in bars].index(tr.entry_date)
    assert idx + MAX_HOLD - 1 <= len(bars)


def test_cost_is_applied_in_r():
    bars = _flat(20) + _bars([(100, 101, 99, 100), (100, 200, 99, 150)])
    sig = [False] * (len(bars) - 2) + [True, False]
    tr = simulate_symbol("X", bars, sig, "T")[0]
    risk = 1.2 * 2.0
    gross = (tr.tp - tr.entry) / risk
    assert abs(tr.r_net - (gross - COST_PCT * tr.entry / risk)) < 1e-6


# ------------------------------------------------------------ tavan
def _t(sym, day, exit_day):
    return Trade(strategy="S", symbol=sym, signal_date=day, entry_date=day,
                 entry=10, stop=9, tp=11, exit_date=exit_day, r_net=0.1,
                 outcome="WIN")


def test_daily_cap_limits_new_entries():
    trades = [_t(f"S{i}", "2026-08-04", "2026-08-05") for i in range(10)]
    kept = apply_caps(trades, max_daily=3, max_open=10)
    assert len(kept) == 3
    assert [k.symbol for k in kept] == ["S0", "S1", "S2"]   # deterministik


def test_open_cap_blocks_when_slots_full():
    long_open = [_t(f"A{i}", "2026-08-04", "2026-12-31") for i in range(4)]
    later = [_t(f"B{i}", "2026-08-05", "2026-08-06") for i in range(4)]
    kept = apply_caps(long_open + later, max_daily=6, max_open=4)
    assert len(kept) == 4                     # 4 slot dolu, ertesi gun yer yok
    assert all(k.symbol.startswith("A") for k in kept)


def test_slots_free_up_after_exit():
    first = [_t("A0", "2026-08-04", "2026-08-04")]
    second = [_t("B0", "2026-08-05", "2026-08-05")]
    kept = apply_caps(first + second, max_daily=6, max_open=1)
    assert len(kept) == 2


# ----------------------------------------------------------- ozet
def test_summary_cohort_window_filters_old_trades():
    old = Trade("S", "X", "2026-07-01", "2026-07-02", 10, 9, 11,
                exit_date="2026-07-03", r_net=5.0, outcome="WIN")
    new = Trade("S", "X", "2026-08-05", "2026-08-06", 10, 9, 11,
                exit_date="2026-08-07", r_net=-1.0, outcome="LOSS")
    assert summarize([old, new])["n"] == 2
    k = summarize([old, new], since="2026-08-04")
    assert k["n"] == 1 and k["net_r"] == -1.0


def test_summary_max_drawdown():
    tr = [Trade("S", "X", "d", "d", 1, 1, 1, exit_date=f"2026-08-0{i}",
                r_net=r, outcome="W") for i, r in enumerate([1, -2, -1, 3], 1)]
    s = summarize(tr)
    assert s["net_r"] == 1.0 and s["max_dd_r"] == 3.0     # +1 -> -2 dip


# --------------------------- v3.22: tavan SECIM SIRASI onemli mi?
def test_ranked_cap_prefers_high_score():
    """Tavan devredeyken EN IYI skorlu sinyaller alinmali.
    S4 vakasi: rastgele secimde tavansiz +79R olan strateji -148R'ye
    dusuyordu; kaliteye gore secimde -25R. Secim kurali sonucu
    DEGISTIRIYOR, bu yuzden acikca olculur."""
    def t(sym, score):
        return Trade(strategy="S", symbol=sym, signal_date="2026-08-04",
                     entry_date="2026-08-04", entry=10, stop=9, tp=11,
                     exit_date="2026-08-05", r_net=score, outcome="WIN",
                     score=score)
    trades = [t("ZZZ", 9.0), t("AAA", 1.0), t("MMM", 5.0)]
    ranked = apply_caps(trades, max_daily=2, max_open=10, ranked=True)
    alpha = apply_caps(trades, max_daily=2, max_open=10, ranked=False)
    assert [x.symbol for x in ranked] == ["ZZZ", "MMM"]     # skor sirasi
    assert [x.symbol for x in alpha] == ["AAA", "MMM"]      # alfabetik
    assert sum(x.r_net for x in ranked) > sum(x.r_net for x in alpha)


def test_ranked_is_deterministic_on_ties():
    def t(sym):
        return Trade(strategy="S", symbol=sym, signal_date="d",
                     entry_date="d", entry=10, stop=9, tp=11,
                     exit_date="d", r_net=0.1, outcome="WIN", score=1.0)
    kept = apply_caps([t("B"), t("A"), t("C")], 2, 10, ranked=True)
    assert [x.symbol for x in kept] == ["A", "B"]     # esitlikte alfabetik


# ------------------- v3.23: S5 = S1 girisi + V2 (genis) cikisi
def test_wide_exit_has_no_target_and_survives_v0_stop():
    """V2 profili: hedef YOK, stop 2 ATR, 20 gun. Ayni seride V0
    stop olurken V2 hayatta kalmali (kombinasyonun tum fikri bu)."""
    bars = _flat(20) + _bars([(100, 101, 99, 100),      # sinyal
                              (100, 101, 99, 100),      # giris
                              (100, 101, 97.0, 98)])    # V0 stop bolgesi
    bars += _flat(6, px=105)
    sig = [False] * 20 + [True] + [False] * (len(bars) - 21)
    v0 = simulate_symbol("X", bars, sig, "S1")[0]
    v2 = simulate_symbol("X", bars, sig, "S5", stop_mult=2.0,
                         tp_mult=None, max_hold=20)[0]
    assert v0.outcome == "LOSS"                 # 1.2 ATR stop calisti
    assert v2.outcome != "LOSS"                 # 2.0 ATR stop dayandi
    assert v2.tp == 0.0                         # hedef yok


def test_s5_uses_same_entries_as_s1():
    """S5 AYNI giris sinyallerini kullanir; yalniz cikis farklidir.
    Aksi halde kombinasyon degil, bambaska bir strateji olur."""
    from app.services.strategy_lab import EXEC_OF, STRATEGIES
    assert "S5_MOM_WIDE" in STRATEGIES
    assert EXEC_OF["S1_MOMENTUM"] == "V0" and EXEC_OF["S5_MOM_WIDE"] == "V2"
    from pathlib import Path
    src = Path("app/services/strategy_lab.py").read_text()
    assert 'gens["S5_MOM_WIDE"] = gens["S1_MOMENTUM"]' in src
