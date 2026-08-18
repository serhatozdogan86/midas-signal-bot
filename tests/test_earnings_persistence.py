"""v4.38: bilanco takvimi restart'i atlatir (17-18 Agu ~6 dk olcumu).

VAKA: takvim yalniz bellekteydi; her restart sonrasi yeniden cekilene
kadar (~6 dk, iki saha olcumu) motor fail-closed kaliyordu. Simdi son
BASARILI takvim meta'ya yazilir ve acilista TAZELIK SARTIYLA tohumlanir.

Kirilabilirlik: ilk test eski kodda kirmizi (restart sonrasi ready=False
olurdu); bayatlik testi fail-closed'un DELINMEDIGINI kanitlar - kalicilik
2.2'yi gevsetmek icin bahane degildir.
"""
from __future__ import annotations

import json
import time
from datetime import date

from app.services.database import Database
from app.services.earnings_service import EarningsService, _STALE_SEC
from app.services.market_calendar import MarketCalendar
from app.services.signal_tracker import SignalTracker


class _Finnhub:
    def __init__(self, rows):
        self.rows = rows

    def get_earnings_calendar(self, d_from, d_to):
        return self.rows


def _db(tmp_path):
    db = Database(str(tmp_path / "e.db"))
    SignalTracker(db, "1h")                  # meta tablosu migrasyonu
    return db


def test_restart_sonrasi_takvim_aninda_hazir(tmp_path):
    """Tam donus turu: basarili cekim -> 'restart' (yeni instance, OLU
    Finnhub) -> takvim meta'dan tohumlanir, ready ANINDA True. Eski
    kodda ikinci instance ready=False kalirdi (~6 dk pencere)."""
    db = _db(tmp_path)
    rows = [{"symbol": "AAPL", "date": "2026-08-25"},
            {"symbol": "MSFT", "date": "2026-08-27"}]
    a = EarningsService(_Finnhub(rows), MarketCalendar(), db=db)
    a.refresh(date(2026, 8, 18), force=True)
    assert a.status()["ready"] is True

    b = EarningsService(_Finnhub([]), MarketCalendar(), db=db)  # restart
    st = b.status()
    assert st["ready"] is True                 # pencere KAPANDI
    assert st["symbols"] == 2
    info = b.info("AAPL", date(2026, 8, 24))
    assert info.available is True
    assert info.next_date == "2026-08-25"      # tohumlanan tarih kullanimda


def test_bayat_kopya_tohumlanmaz_fail_closed_korunur(tmp_path):
    """Kalicilik 2.2'yi delmez: meta'daki kopya _STALE_SEC'ten eskiyse
    YOK sayilir - restart sonrasi bot yine fail-closed baslar."""
    db = _db(tmp_path)
    old = time.time() - _STALE_SEC - 60
    db.execute(
        "INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)",
        (EarningsService._META_KEY, json.dumps(
            {"last_ok": old, "fetched_at": old,
             "dates": {"AAPL": ["2026-08-25"]}})))
    b = EarningsService(_Finnhub([]), MarketCalendar(), db=db)
    assert b.status()["ready"] is False        # bayat kopyaya guven YOK


def test_basarisiz_cekim_iyi_kopyayi_ezmez(tmp_path):
    """Gist '[]' vakasinin dersi: bos/basarisiz cekim meta'daki son iyi
    takvimi ASLA ezmez; sonraki restart yine iyi kopyayla acilir."""
    db = _db(tmp_path)
    a = EarningsService(_Finnhub([{"symbol": "AAPL", "date": "2026-08-25"}]),
                        MarketCalendar(), db=db)
    a.refresh(date(2026, 8, 18), force=True)
    a._finnhub = _Finnhub([])                  # kaynak coktu
    a.refresh(date(2026, 8, 18), force=True)   # basarisiz cekim
    saved = json.loads(db.query_one(
        "SELECT value FROM meta WHERE key=?",
        (EarningsService._META_KEY,))["value"])
    assert saved["dates"] == {"AAPL": ["2026-08-25"]}   # iyi kopya duruyor
    c = EarningsService(_Finnhub([]), MarketCalendar(), db=db)
    assert c.status()["ready"] is True


def test_db_verilmezse_eski_davranis(tmp_path):
    """db=None (testler/eski cagiranlar): kalicilik sessizce devre disi,
    hicbir sey kirilmaz."""
    a = EarningsService(_Finnhub([]), MarketCalendar())
    assert a.status()["ready"] is False
