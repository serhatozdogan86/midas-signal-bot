"""v4.40: Finnhub takvim kirpmasi (704 sorusturmasinin cozumu, 18 Agu).

OLCULEN VAKA: /calendar/earnings ~1500 satirda sessizce kirper ve
kirptigi yer pencerenin BASI - en yakin tarihler atilir (hata/uyari yok).
Sezon zirvesinde karartmanin baktigi +-2 is gunu fiilen takvimden dustu:
5 sinyal karartma icinde dogdu (BMY/PCAR/AMGN/HWM/ALL, -3.35R; hepsi
kilit-2 ONCESI - go-live kohortu temiz).

DUZELTME: pencere 3'er gunluk dilimlerle cekilir + kanarya (dilim tavana
dayanirsa cap_suspect) + 16. degismez (takvim kapsamasi).
Kirilabilirlik: ilk test eski kodda KIRMIZI - tek-istek yol, kirpan sahte
saglayicidan en yakin gunleri alamazdi.
"""
from __future__ import annotations

from datetime import date, timedelta

from app.services.earnings_service import EarningsService
from app.services.market_calendar import MarketCalendar
from app.services.self_audit import run_audit
from app.services.signal_tracker import SignalTracker
from app.services.database import Database

_CAP = 1500


class _CappingFinnhub:
    """Olculen Finnhub davranisinin taklidi: istenen araligin satirlarini
    tarihe gore siralar ve tavani asarsa EN ERKEN tarihleri atar."""

    def __init__(self, per_day: int):
        self.per_day = per_day
        self.calls: list[tuple[str, str]] = []

    def get_earnings_calendar(self, d_from: str, d_to: str):
        self.calls.append((d_from, d_to))
        start, end = date.fromisoformat(d_from), date.fromisoformat(d_to)
        rows = []
        d = start
        while d <= end:
            for i in range(self.per_day):
                rows.append({"symbol": f"{d.isoformat()}-{i}",
                             "date": d.isoformat()})
            d += timedelta(days=1)
        return rows[-_CAP:] if len(rows) > _CAP else rows   # basi kirpilir


def test_dilimli_cekim_en_yakin_tarihleri_kaybetmez(tmp_path):
    """Sezon zirvesi: gunde 200 satir x 19 gun = 3800 >> 1500. Eski tek
    istek en yakin ~8 gunu kaybederdi; dilimli cekim TAMAMINI alir."""
    fh = _CappingFinnhub(per_day=200)
    svc = EarningsService(fh, MarketCalendar())
    today = date(2026, 8, 4)                     # sezon ici bir gun
    svc.refresh(today, force=True)
    st = svc.status()
    assert st["ready"] is True
    assert st["symbols"] == 19 * 200             # HIC kayip yok
    # kritik kanit: pencerenin ILK gunu (kirpilan bolge) takvimde
    first_day = (today - timedelta(days=4)).isoformat()
    info = svc.info(f"{first_day}-0", today)
    assert info.next_date == first_day
    assert st["cap_suspect"] is False            # dilimler tavanin altinda
    assert len(fh.calls) >= 6                    # gercekten dilim dilim


def test_kanarya_dilim_tavana_dayaninca_oter(tmp_path):
    """Bir dilim bile tavana dayanirsa veri 'tam' sayilamaz - kanarya
    yanar ve 16. degismez (takvim kapsamasi) KIRMIZI olur."""
    fh = _CappingFinnhub(per_day=500)            # 3 gunluk dilim = 1500
    svc = EarningsService(fh, MarketCalendar())
    svc.refresh(date(2026, 8, 4), force=True)
    assert svc.status()["cap_suspect"] is True

    db = Database(str(tmp_path / "a.db"))
    SignalTracker(db, "1h")
    rep = run_audit(db=db, earnings=svc)
    cov = [c for c in rep.checks if c.name == "takvim kapsamasi"][0]
    assert cov.ok is False and cov.severity == "critical"


def test_normal_gunde_kapsama_yesil(tmp_path):
    fh = _CappingFinnhub(per_day=30)             # sezon disi yogunluk
    svc = EarningsService(fh, MarketCalendar())
    svc.refresh(date(2026, 8, 18), force=True)
    assert svc.status()["cap_suspect"] is False
    db = Database(str(tmp_path / "b.db"))
    SignalTracker(db, "1h")
    rep = run_audit(db=db, earnings=svc)
    cov = [c for c in rep.checks if c.name == "takvim kapsamasi"][0]
    assert cov.ok is True
