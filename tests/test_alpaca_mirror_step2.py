"""AYNA ADIM 2 (v4.24) - emir yasam dongusu, sahte istemciyle.

Ayna INCE transkripsiyon katmanidir: broker'in soyledigini yazar,
pencere/time-stop tetiklerini kosar, SIMULASYON YAPMAZ. Burada olculenler:
gonderim (yon/limit/qty), dolum-cikis transkripsiyonu, 14 barlik pencere
iptali, 28 barlik time-stop kapamasi, kapali/istemcisiz atalet ve
izolasyonun (defter semasi) bozulmadigi.
"""
from __future__ import annotations

from app.services.alpaca_mirror import AlpacaMirror
from app.services.database import Database
from app.services.signal_tracker import SignalTracker


class FakeClient:
    """Istemci sozlesmesinin testlik uygulamasi (adim 3'un provasi)."""

    def __init__(self):
        self.orders: dict = {}
        self.cancelled: list = []
        self.closed: list = []
        self._n = 0

    def submit_bracket(self, symbol, side, qty, limit, stop, tp):
        self._n += 1
        oid = f"o{self._n}"
        self.orders[oid] = {"symbol": symbol, "side": side, "qty": qty,
                            "limit": limit, "stop": stop, "tp": tp,
                            "status": "new", "fill_price": None,
                            "fill_ts": None, "exit_price": None,
                            "exit_ts": None, "exit_reason": None}
        return oid

    def order_status(self, oid):
        return dict(self.orders[oid]) if oid in self.orders else None

    def cancel(self, oid):
        self.cancelled.append(oid)
        if oid in self.orders:
            self.orders[oid]["status"] = "canceled"
        return True

    def close_position(self, symbol, qty):
        self.closed.append((symbol, qty))
        return {"price": 101.5, "ts": 99000}


def _setup(tmp_path, client=None, enabled=True):
    db = Database(str(tmp_path / "m.db"))
    SignalTracker(db, "1h")                       # migrasyon
    m = AlpacaMirror(db, enabled=enabled, client=client)
    return db, m


def _signal_row(db, symbol="AAPL", direction="LONG", entry_min=100.0,
                entry_max=101.0, stop=98.0, tp1=104.0, entry_ts=1000):
    db.execute(
        "INSERT INTO signals(symbol,direction,created_utc,entry_candle_ts,"
        "entry_min,entry_max,stop_loss,tp1,status,blocked) "
        "VALUES(?,?,?,?,?,?,?,?, 'PENDING',0)",
        (symbol, direction, "2026-08-08T14:00:00Z", entry_ts,
         entry_min, entry_max, stop, tp1))
    return db.query_one("SELECT * FROM signals ORDER BY id DESC LIMIT 1")


def _candles(db, symbol, n, start_ts=1000, step=1000):
    db.executemany(
        "INSERT OR IGNORE INTO candles(symbol,interval,ts,open,high,low,"
        "close,volume) VALUES(?,?,?,?,?,?,?,?)",
        [(symbol, "1h", start_ts + (i + 1) * step, 100, 101, 99, 100, 1000)
         for i in range(n)])


def test_sinyal_gonderilir_yon_limit_qty_dogru(tmp_path):
    db, m = _setup(tmp_path, FakeClient())
    row = _signal_row(db)
    assert m.sync_signals([row]) == 1
    o = list(m._client.orders.values())[0]
    assert o["side"] == "buy"
    assert o["limit"] == 101.0                    # LONG: kotu uc entry_max
    assert abs(o["qty"] - 100.0 / 3.0) < 0.01     # 100$ risk / (101-98)
    assert o["stop"] == 98.0 and o["tp"] == 104.0
    # dedup: ayni sinyal ikinci sync'te yeniden gonderilmez
    assert m.sync_signals([row]) == 0
    mf = db.query_one("SELECT * FROM mirror_fills")
    assert mf["alpaca_status"] == "SUBMITTED" and mf["qty"] > 0


def test_short_aynalanir(tmp_path):
    db, m = _setup(tmp_path, FakeClient())
    row = _signal_row(db, symbol="NVDA", direction="SHORT",
                      entry_min=120.0, entry_max=121.0, stop=125.0, tp1=114.0)
    assert m.sync_signals([row]) == 1
    o = list(m._client.orders.values())[0]
    assert o["side"] == "sell"
    assert o["limit"] == 120.0                    # SHORT: kotu uc entry_min


def test_dolum_ve_cikis_transkripsiyonu(tmp_path):
    db, m = _setup(tmp_path, fc := FakeClient())
    row = _signal_row(db)
    m.sync_signals([row])
    oid = next(iter(fc.orders))
    fc.orders[oid].update(status="filled", fill_price=100.8, fill_ts=5000)
    m.poll()
    assert db.query_one("SELECT * FROM mirror_fills")["alpaca_status"] == "FILLED"
    fc.orders[oid].update(status="closed", exit_price=104.0, exit_ts=9000,
                          exit_reason="TP")
    m.poll()
    mf = db.query_one("SELECT * FROM mirror_fills")
    assert mf["alpaca_status"] == "CLOSED"
    assert mf["alpaca_fill_price"] == 100.8
    assert mf["alpaca_exit_price"] == 104.0 and mf["closed_reason"] == "TP"


def test_pencere_dolunca_iptal(tmp_path):
    db, m = _setup(tmp_path, fc := FakeClient())
    row = _signal_row(db, entry_ts=1000)
    m.sync_signals([row])
    _candles(db, "AAPL", 14, start_ts=1000)       # 14 kapanmis bar gecti
    m.poll()
    mf = db.query_one("SELECT * FROM mirror_fills")
    assert mf["alpaca_status"] == "CANCELLED"
    assert mf["closed_reason"] == "WINDOW"
    assert fc.cancelled                            # iptal broker'a iletildi


def test_time_stop_pozisyonu_kapatir(tmp_path):
    db, m = _setup(tmp_path, fc := FakeClient())
    row = _signal_row(db, entry_ts=1000)
    m.sync_signals([row])
    oid = next(iter(fc.orders))
    fc.orders[oid].update(status="filled", fill_price=100.8, fill_ts=2000)
    m.poll()                                       # FILLED
    _candles(db, "AAPL", 28, start_ts=2000)        # dolumdan 28 bar
    m.poll()
    mf = db.query_one("SELECT * FROM mirror_fills")
    assert mf["alpaca_status"] == "CLOSED" and mf["closed_reason"] == "TIME"
    assert fc.closed and fc.closed[0][0] == "AAPL"
    assert mf["alpaca_exit_price"] == 101.5


def test_istemcisiz_yalniz_niyet_kapaliyken_hicbir_sey(tmp_path):
    db, m = _setup(tmp_path, client=None, enabled=True)
    row = _signal_row(db)
    assert m.sync_signals([row]) == 0              # gonderim yok
    assert db.query_one("SELECT * FROM mirror_fills")["alpaca_status"] == "INTENT"
    db2, m2 = _setup(tmp_path.joinpath("k"), FakeClient(), enabled=False)
    row2 = _signal_row(db2)
    assert m2.sync_signals([row2]) == 0
    assert db2.query_one("SELECT COUNT(*) n FROM mirror_fills")["n"] == 0


def test_izolasyon_bozulmadi(tmp_path):
    """Adim 2 sonrasi da: signals semasina alan sizmadi, ayna kendi
    tablosunda (13. degismez yesil kalir)."""
    db, m = _setup(tmp_path, FakeClient())
    row = _signal_row(db)
    m.sync_signals([row])
    cols = [r["name"] for r in db.query("PRAGMA table_info(signals)")]
    assert not [c for c in cols if "mirror" in c.lower() or "alpaca" in c.lower()]


def test_tick_kablolamasi_bayrak_ve_istemciye_bagli():
    from pathlib import Path
    src = Path("app/scheduler.py").read_text(encoding="utf-8")
    tick = src[src.index("    def tick(self"):src.index("    def run_prep(")]
    assert "_mirror" in tick and "mirror.enabled" in tick.replace("self._", "")
    main_src = Path("app/main.py").read_text(encoding="utf-8")
    assert "ALPACA_MIRROR_ENABLED" in main_src
