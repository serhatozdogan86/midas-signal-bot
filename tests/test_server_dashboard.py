"""Server smoke testleri: dashboard + Faz 3 endpoint'leri."""
from __future__ import annotations

from app.config.settings import Settings
from app.scheduler import Scheduler
from app.server import create_app
from app.services.database import Database
from app.services.market_calendar import MarketCalendar
from app.services.signal_tracker import SignalTracker
from app.services.state_store import InMemoryStateStore


class _NoopNotifier:
    def send(self, text):
        return True


def _client(tmp_path, tracker=None, gist_backup=None):
    settings = Settings(TELEGRAM_ENABLED=False, STATE_BACKEND="memory")
    store = InMemoryStateStore()
    sched = Scheduler(settings, None, None, None, MarketCalendar(),
                      store, _NoopNotifier(), tracker, gist_backup)
    app = create_app(store, sched, universe=None, tracker=tracker,
                     gist_backup=gist_backup)
    return app.test_client()


def test_dashboard_served(tmp_path):
    c = _client(tmp_path)
    for path in ("/", "/dashboard"):
        r = c.get(path)
        assert r.status_code == 200
        assert b"midas" in r.data and b"Equity" in r.data
        assert b"--bg:#141110" in r.data                 # koyu tema
        assert b"Haber Akisi" in r.data                  # haber paneli
        assert b"Portfoy Simulasyonu" in r.data
        assert b"Nasil okunur?" in r.data
        assert b"Aksiyon Paneli" in r.data
        assert b"Takvim Seridi" in r.data
        assert b"Gap Nobeti" in r.data
        assert b"Pozisyon buyuklugu" in r.data
        assert b"JetBrains+Mono" in r.data           # terminal tipografi
        assert b"data-tip" in r.data                 # tooltip sistemi
        assert b"STAGE_TIPS" in r.data               # boru hatti aciklamalari
        assert b"simSlot" in r.data                  # kapasite modu
        assert b"fontStep" in r.data                 # yazi boyutu secici
        assert b">Kalite<" in r.data and b">Canli<" in r.data


def test_news_endpoint(tmp_path):
    from datetime import date
    from app.services.news_service import NewsService
    from tests.test_news_service import FakeFinnhubNews

    news = NewsService(FakeFinnhubNews(), refresh_sec=0)
    news.refresh(["AAPL"], date(2026, 7, 29))
    settings = Settings(TELEGRAM_ENABLED=False, STATE_BACKEND="memory")
    store = InMemoryStateStore()
    sched = Scheduler(settings, None, None, None, MarketCalendar(),
                      store, _NoopNotifier(), None, None, None, news)
    app = create_app(store, sched, universe=None, news=news)
    c = app.test_client()
    body = c.get("/news").get_json()
    assert body["info"]["count"] >= 3
    assert any(i["symbol"] == "AAPL" for i in body["items"])
    assert c.get("/diag").get_json()["news"]["count"] >= 3


def test_performance_and_signals_with_tracker(tmp_path):
    tracker = SignalTracker(Database(str(tmp_path / "t.db")), "1h")
    c = _client(tmp_path, tracker=tracker)
    r = c.get("/performance")
    assert r.status_code == 200 and r.get_json()["open_signals"] == 0
    r = c.get("/signals?limit=5")
    assert r.status_code == 200 and r.get_json() == []


def test_live_and_candles_endpoints(tmp_path):
    tracker = SignalTracker(Database(str(tmp_path / "t.db")), "1h")
    c = _client(tmp_path, tracker=tracker)
    body = c.get("/live").get_json()
    assert body["rows"] == [] and body["session"]["phase"]
    assert c.get("/candles?symbol=AAPL").get_json() == []
    diag = c.get("/diag").get_json()
    assert "session" in diag and "calendar_strip" in diag


def test_endpoints_404_when_disabled(tmp_path):
    c = _client(tmp_path)
    assert c.get("/performance").status_code == 404
    assert c.get("/backup/info").status_code == 404


def test_diag_endpoint_and_embedded_block(tmp_path):
    import json as _json
    import logging

    from app.logging_setup import get_ring_buffer
    get_ring_buffer()
    logging.getLogger("testdiag").warning("ornek uyari kaydi")

    tracker = SignalTracker(Database(str(tmp_path / "t.db")), "1h")
    c = _client(tmp_path, tracker=tracker)

    r = c.get("/diag")
    assert r.status_code == 200
    diag = r.get_json()
    assert "meta" in diag and "regime" in diag and "shadow" in diag
    assert diag["log_counts"]["WARNING"] >= 1
    assert any("ornek uyari" in w["msg"] for w in diag["recent_warnings"])

    # dashboard sayfasina gomulu server-diag blogu (uzaktan tani sozlesmesi)
    r = c.get("/")
    assert b'id="server-diag"' in r.data
    assert b"DURUM OZETI ::" in r.data          # gorunur ozet satiri
    assert b"/diag</a>" in r.data               # tam adresli detay linki
    raw = r.data.split(b'id="server-diag">')[1].split(b"</script>")[0]
    embedded = _json.loads(raw.decode().replace("<\\/", "</"))
    assert "regime" in embedded and "log_counts" in embedded
