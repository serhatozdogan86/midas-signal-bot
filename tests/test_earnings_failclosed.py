"""v3.16: bilanco takvimi yuklenemediginde GUVENLI TARAF.

3 Agustos vakasi: prep sirasinda /calendar/earnings timeout'a dustu,
_dates bos kaldi ve bilanco filtresi TUM SEANS sessizce devre disi
kaldi. Sonuc: AMGN'e bilancosuna 1 islem gunu kala LONG sinyali
uretildi. TTL 6 saat oldugu icin yeniden deneme de olmadi.
"""
from __future__ import annotations

from datetime import date

from app.config.settings import Settings
from app.models.decision import DecisionType, EarningsInfo
from app.services.earnings_service import EarningsService
from app.services.market_calendar import MarketCalendar


class _FH:
    """v4.40 uyumu: refresh artik pencereyi DILIMLERLE ceker (kirpma
    korumasi), yani bir refresh birden cok cagri yapar. 'failing' bayragi
    TAM kesintiyi taklit eder (tum dilimler bos); calls ham cagri sayar."""

    def __init__(self, rows=None, failing=False):
        self.rows = rows or []
        self.failing = failing
        self.calls = 0

    def get_earnings_calendar(self, d_from, d_to):
        self.calls += 1
        if self.failing:
            return []
        return self.rows


_ROWS = [{"symbol": "AMGN", "date": "2026-08-04"}]


def test_service_not_ready_when_first_fetch_fails():
    svc = EarningsService(_FH(failing=True), MarketCalendar())
    svc.refresh(date(2026, 8, 3))
    assert svc.status()["ready"] is False
    info = svc.info("AMGN", date(2026, 8, 3))
    assert info.available is False          # "bilanco yok" DEGIL "bilmiyoruz"


def test_service_retries_quickly_when_not_ready(monkeypatch):
    fh = _FH(_ROWS, failing=True)
    svc = EarningsService(fh, MarketCalendar())
    svc.refresh(date(2026, 8, 3))           # 1. deneme: tam kesinti
    assert fh.calls >= 1 and svc.status()["ready"] is False
    import app.services.earnings_service as mod
    monkeypatch.setattr(mod, "_RETRY_SEC", 0)
    fh.failing = False                      # kaynak toparladi
    svc.refresh(date(2026, 8, 3))           # TTL beklemeden tekrar dener
    assert svc.status()["ready"] is True
    assert svc.info("AMGN", date(2026, 8, 3)).available is True


def test_ready_service_does_not_refetch_within_ttl():
    fh = _FH(_ROWS)
    svc = EarningsService(fh, MarketCalendar())
    svc.refresh(date(2026, 8, 3))
    first = fh.calls                        # v4.40: dilim sayisi kadar
    svc.refresh(date(2026, 8, 3))
    assert fh.calls == first                # TTL korunur: yeni cagri yok


def _engine_decision(earnings, fail_closed=True):
    """Gercek LONG boru hattini kuran fixture'lari kullanir; boylece
    sinyal SADECE bilanco filtresi yuzunden dusmelidir."""
    from app.models.decision import MarketRegime
    from app.strategies import signal_engine
    from app.strategies.regime_detector import RegimeResult
    from tests import fixtures as fx
    daily = fx.make_series(fx.daily_uptrend_closes(), interval="1d",
                           symbol="AMGN", spread=0.02)
    hourly = fx.make_series(fx.hourly_pullback_long_closes(), symbol="AMGN",
                            volumes=fx.spike_volumes(110))
    bench = fx.make_series(fx.daily_uptrend_closes(), interval="1d",
                           symbol="SPY").to_dataframe()
    params = Settings(EARNINGS_FAIL_CLOSED=fail_closed).strategy_params
    return signal_engine.evaluate("AMGN", daily, hourly,
                                  RegimeResult(regime=MarketRegime.BULL),
                                  params, bench, earnings)


def test_engine_blocks_when_calendar_unavailable():
    d = _engine_decision(EarningsInfo(available=False))
    assert d.decision is not DecisionType.SIGNAL
    assert "EARNINGS" in (d.failed_filters or [])
    assert "guvenli taraf" in (d.reject_reason or "")


def test_engine_can_be_switched_to_fail_open():
    """Esik yapilandirilabilir: kapatilirsa eski (riskli) davranis
    geri gelir ve sinyal uretilir - karar kullanicinin."""
    d = _engine_decision(EarningsInfo(available=False), fail_closed=False)
    assert d.decision is DecisionType.SIGNAL


def test_known_earnings_still_blocks_normally():
    d = _engine_decision(EarningsInfo(next_date="2026-08-04", days_to=1))
    assert d.decision is not DecisionType.SIGNAL
    assert "blackout" in (d.reject_reason or "")


# ---------------------------------------- v3.18 yedek kaynak (yfinance)
def _svc(fallback=None, fh_rows=None):
    return EarningsService(_FH(fh_rows or []), MarketCalendar(),
                           fallback=fallback)


def test_fallback_fills_gap_when_finnhub_down():
    """Finnhub takvimi cokse bile yedek kaynak AMGN'i yakalamali -
    3 Agu vakasinin tekrarlanmamasi icin."""
    svc = _svc(fallback=lambda s: [date(2026, 8, 4)] if s == "AMGN" else [])
    svc.refresh(date(2026, 8, 3))
    assert svc.status()["ready"] is False
    assert svc.info("AMGN", date(2026, 8, 3)).available is False   # yedek yok
    svc.prefetch(["AMGN", "MSFT"], date(2026, 8, 3))
    got = svc.info("AMGN", date(2026, 8, 3))
    assert got.available is True and got.next_date == "2026-08-04"
    assert got.days_to == 1                       # blackout penceresinde
    assert svc.info("MSFT", date(2026, 8, 3)).next_date is None


def test_fallback_error_stays_unknown_not_empty():
    """Yedek kaynak HATA verirse 'bilanco yok' degil 'bilmiyoruz'."""
    svc = _svc(fallback=lambda s: None)
    svc.refresh(date(2026, 8, 3))
    svc.prefetch(["AMGN"], date(2026, 8, 3))
    assert svc.info("AMGN", date(2026, 8, 3)).available is False
    assert svc.status()["fallback_failed"] == 1


def test_pass1_not_locked_out_when_calendar_missing():
    """KILITLENME KORUMASI: pass-1 strict=False ile eleme yapmaz; aksi
    halde hicbir aday pass-2'ye ulasmaz ve yedek kaynak hic calismaz."""
    svc = _svc(fallback=lambda s: [])
    svc.refresh(date(2026, 8, 3))
    assert svc.info("AAPL", date(2026, 8, 3), strict=False).available is True
    assert svc.info("AAPL", date(2026, 8, 3)).available is False


def test_fallback_not_used_when_finnhub_ready():
    calls = []
    svc = _svc(fallback=lambda s: calls.append(s) or [], fh_rows=_ROWS)
    svc.refresh(date(2026, 8, 3))
    svc.prefetch(["AMGN", "MSFT"], date(2026, 8, 3))
    assert calls == []                            # gereksiz maliyet yok


def test_fallback_caches_per_day():
    calls = []
    svc = _svc(fallback=lambda s: calls.append(s) or [])
    svc.refresh(date(2026, 8, 3))
    svc.prefetch(["AMGN"], date(2026, 8, 3))
    svc.prefetch(["AMGN"], date(2026, 8, 3))
    assert calls == ["AMGN"]                      # ikinci cagri onbellekten
