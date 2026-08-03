"""v3.19 cikis laboratuvari testleri.

EN KRITIK: test_v0_mirrors_live - laboratuvar canli parametrelerle
kosturuldugunda SignalTracker ile AYNI sonucu vermeli. Vermezse
V1/V2 kiyasi anlamsizdir (farkli dolum/gap kurallari kiyasi kirletir).
"""
from __future__ import annotations

import numpy as np

from app.services.database import Database
from app.services.exit_lab import (VARIANTS, ExitLab, LabResult, replay)
from app.services.signal_tracker import SignalTracker
from tests import fixtures as fx


def _sig(direction="LONG", entry_min=100.0, entry_max=101.0,
         stop=98.0, tp1=104.0, tp2=107.0, sid=1):
    return {"id": sid, "symbol": "AAPL", "direction": direction,
            "entry_min": entry_min, "entry_max": entry_max,
            "stop_loss": stop, "tp1": tp1, "tp2": tp2,
            "entry_candle_ts": 0, "status": "PENDING", "outcome": None,
            "fill_price": None, "r_multiple": None,
            "created_utc": "2026-08-04T00:00:00Z"}


def _c(ts, o, h, low, cl):
    return {"ts": ts, "open": o, "high": h, "low": low, "close": cl,
            "volume": 1e6}


def _fill_bar(ts=1):
    # bolge 100-101 TAMAMEN katedilir -> dolum 101 (kotu uc)
    return _c(ts, 101.5, 102.0, 99.9, 100.5)


# ------------------------------------------------- V0 ayna (kritik)
def test_v0_mirrors_live_on_same_data():
    """Ayni sinyal + ayni mumlar: canli tracker ile 'canli parametreli
    replay' AYNI outcome ve R vermeli."""
    import tempfile
    db = Database(tempfile.mktemp(suffix=".db"))
    tr = SignalTracker(db, "1h")
    # canli parametreli sanal varyant
    VARIANTS["V0_TEST"] = {"mode": "partial", "tp1_frac": 1.0,
                           "rest_max_bars": 999}
    try:
        cases = [
            # (mumlar, beklenen_outcome)
            ([_fill_bar(), _c(2, 100, 104.5, 99.5, 104)], "WIN"),     # TP
            ([_fill_bar(), _c(2, 99, 100, 97.5, 98.5)], "LOSS"),      # STOP
            ([_fill_bar(), _c(2, 96, 97, 95.5, 96.5)], "LOSS"),       # GAP stop
            ([_fill_bar(), _c(2, 105, 106, 104.8, 105.5)], "WIN"),    # GAP TP (lehte)
            ([_fill_bar(), _c(2, 100, 104.2, 97.9, 100)], "AMBIGUOUS"),
        ]
        for candles, expected in cases:
            sig = _sig()
            res = replay(sig, candles, "V0_TEST", fill_window=12)
            assert res.outcome == expected, (expected, res)
            # canli tracker ayni veriyle
            db.execute("DELETE FROM signals")
            db.execute(
                "INSERT INTO signals(id,symbol,direction,created_utc,"
                "entry_candle_ts,entry_min,entry_max,stop_loss,tp1,tp2,"
                "status) VALUES(1,'AAPL','LONG','x',0,100,101,98,104,107,"
                "'PENDING')")
            tr._evaluate_signal(db.query_one("SELECT * FROM signals"), candles)
            live = db.query_one("SELECT * FROM signals")
            assert live["outcome"] == expected, (expected, live["outcome"])
            if expected in ("WIN", "LOSS"):
                assert abs((res.r_gross or 0) - (live["r_multiple"] or 0)) < 0.02
    finally:
        VARIANTS.pop("V0_TEST", None)


def test_fill_requires_full_zone_traversal():
    sig = _sig()
    # yalniz yakin uca dokunur (low 100.4 > entry_min 100) -> dolum YOK
    res = replay(sig, [_c(1, 101.2, 101.6, 100.4, 101.0)] * 12, "V2_GENIS", 12)
    assert res.outcome == "NOT_FILLED"


# ------------------------------------------------------ V1 kismi
def test_v1_partial_takes_half_at_tp1_then_tp2():
    sig = _sig()
    candles = [_fill_bar(),
               _c(2, 102, 104.5, 101.5, 104),     # TP1 -> %50
               _c(3, 104, 107.5, 103.8, 107)]     # TP2 -> kalan %50
    res = replay(sig, candles, "V1_KISMI", 12)
    assert res.outcome == "WIN" and res.status == "CLOSED"
    # dolum 101, risk 3: TP1 (104) = +1R * 0.5; TP2 (107) = +2R * 0.5 => 1.5R
    assert abs(res.r_gross - 1.5) < 0.01
    assert [L["why"] for L in res.legs] == ["TP", "TP"]
    # maliyet: 3 bacak sabit ucret + kayma -> r_net < r_gross
    assert res.r_net < res.r_gross


def test_v1_stop_after_partial_still_positive_possible():
    sig = _sig()
    candles = [_fill_bar(),
               _c(2, 102, 104.5, 101.5, 104),     # TP1 %50 (+0.5R)
               _c(3, 100, 101, 97.5, 98)]         # kalan stop (-1R * 0.5)
    res = replay(sig, candles, "V1_KISMI", 12)
    assert res.status == "CLOSED"
    assert abs(res.r_gross - 0.0) < 0.01          # +0.5 - 0.5
    assert res.outcome == "WIN"                   # r>=0 -> WIN etiketi


# ------------------------------------------------------ V2 genis
def test_v2_wide_survives_v0_stop_and_rides():
    """V0'in stop'unda (98) V2 durmaz; genis stop = 101 - (5/3)*3 = 96."""
    sig = _sig()
    candles = [_fill_bar(),
               _c(2, 99, 100, 97.6, 98.0),        # V0 stop olurdu; V2 devam
               _c(3, 100, 106, 99.5, 105.5),
               _c(4, 106, 110, 105.5, 109.0)]
    res = replay(sig, candles, "V2_GENIS", 12)
    assert res.status == "FILLED"                 # hedef yok, zaman dolmadi
    # zaman asimina zorla: 140 bar duz seri
    tail = [_c(5 + i, 109, 109.5, 108.5, 109.0) for i in range(141)]
    res2 = replay(sig, candles + tail, "V2_GENIS", 12)
    assert res2.outcome == "EXPIRED"
    # R tabani CANLI risk (3 puan): (109-101)/3 ≈ +2.67R
    assert res2.r_gross > 2.5


def test_v2_r_denominator_is_live_risk_for_comparability():
    sig = _sig()
    candles = [_fill_bar(), _c(2, 95.5, 96.5, 95.0, 95.8)]   # genis stop gap
    res = replay(sig, candles, "V2_GENIS", 12)
    assert res.outcome == "LOSS"
    # cikis ~95.5 acilis; (95.5-101)/3 ≈ -1.83R (payda canli risk)
    assert -2.1 < res.r_gross < -1.6


# ------------------------------------------------------ servis
def test_exit_lab_service_upsert_and_summary(tmp_path):
    import time
    db = Database(str(tmp_path / "lab.db"))
    tr = SignalTracker(db, "1h")
    lab = ExitLab(db, md=None, tracker=tr)

    class MD:
        def get_hourly_bulk(self, syms):
            return {}
    lab._md = MD()
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    db.execute(
        "INSERT INTO signals(symbol,direction,created_utc,entry_candle_ts,"
        "entry_min,entry_max,stop_loss,tp1,tp2,status) "
        "VALUES('AAPL','LONG',?,0,100,101,98,104,107,'PENDING')", (now_iso,))
    for i, c in enumerate([_fill_bar(1), _c(2, 102, 104.5, 101.5, 104),
                           _c(3, 104, 107.5, 103.8, 107)]):
        db.execute("INSERT INTO candles(symbol,interval,ts,open,high,low,"
                   "close,volume) VALUES('AAPL','1h',?,?,?,?,?,?)",
                   (c["ts"], c["open"], c["high"], c["low"], c["close"],
                    c["volume"]))
    out = lab.run()
    assert out["signals"] == 1
    s = lab.summary()
    assert s["variants"]["V1_KISMI"]["n_decided"] == 1
    assert s["variants"]["V1_KISMI"]["net_r"] > 1.0
    assert "V0_CANLI" in s["variants"]
    # idempotent: ikinci kosum kapali varyanti yeniden yazmaz
    row1 = db.query_one("SELECT updated FROM exit_lab WHERE variant='V1_KISMI'")
    lab.run()
    row2 = db.query_one("SELECT updated FROM exit_lab WHERE variant='V1_KISMI'")
    assert row1["updated"] == row2["updated"]
