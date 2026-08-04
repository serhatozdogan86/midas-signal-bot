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
        body = r.data.decode("utf-8")
        assert "M\u0130DAS S\u0130NYAL" in body        # v4 marka
        assert "edge-cache atlatici" in body            # fetch shim'imiz
        assert "\u00d6RNEK VER\u0130" in body          # ornek-veri emniyet bandi
        for endpoint in ("live", "performance", "signals",
                         "candles", "news", "diag"):
            # uc sozlesmesi - sablon yukunde slash'lar \u002F kacisli olabilir
            assert (f"/{endpoint}" in body
                    or f"\\u002F{endpoint}" in body), endpoint


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


def test_no_store_headers_everywhere(tmp_path):
    c = _client(tmp_path)
    for path in ("/", "/healthz", "/diag"):
        assert "no-store" in c.get(path).headers.get("Cache-Control", "")


def test_progress_surfaces_in_diag(tmp_path):
    tracker = SignalTracker(Database(str(tmp_path / "t.db")), "1h")
    c = _client(tmp_path, tracker=tracker)
    assert c.get("/diag").get_json()["progress"] == ""


def test_tape_injected_at_top(tmp_path):
    """v3: DURUM OZETI artik tepedeki altin durum bandinda yasar."""
    c = _client(tmp_path)
    body = c.get("/").get_data(as_text=True)
    assert "DURUM OZETI ::" in body           # kacisli veya duz - icerik sart



def test_dx_plaintext_diag(tmp_path):
    import logging
    from app.logging_setup import get_ring_buffer
    get_ring_buffer()
    logging.getLogger("testdx").error("ornek hata kaydi")
    c = _client(tmp_path)
    body = c.get("/dx").get_data(as_text=True)
    assert "warn=" in body and "err=" in body
    assert "ornek hata kaydi" in body
    r = c.get("/")
    page = r.get_data(as_text=True) if hasattr(r, "get_data") else r.data.decode()
    assert "/dx" in page or "\\u002Fdx" in page       # kesif linki (kacisli olabilir)
    assert "M\u0130DAS S\u0130NYAL" in r.data.decode("utf-8")   # v4 marka
    assert b"edge-cache atlatici" in r.data        # cache-buster


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
    page = r.data.decode("utf-8")
    assert "/diag" in page or "\\u002Fdiag" in page   # detay linki (kacisli olabilir)
    raw = r.data.split(b'id="server-diag">')[1].split(b"</script>")[0]
    embedded = _json.loads(raw.decode().replace("<\\/", "</"))
    assert "regime" in embedded and "log_counts" in embedded



def test_quotes_endpoint_graceful(tmp_path):
    c = _client(tmp_path)
    r = c.get("/quotes?symbols=AAPL,MSFT")
    assert r.status_code == 200
    assert r.get_json() == {}


def test_wallet_sync_and_perf_net(tmp_path):
    from app.services.database import Database
    from app.services.signal_tracker import SignalTracker
    tracker = SignalTracker(Database(str(tmp_path / "w.db")), "1h")
    c = _client(tmp_path, tracker=tracker)
    r = c.post("/wallet", json={"symbols": {"aapl": 10, "PCG": 250}})
    assert r.get_json() == {"ok": True, "count": 2}
    perf = c.get("/performance").get_json()
    assert "net" in perf


def test_fundamentals_endpoint(tmp_path, monkeypatch):
    from app.services.fundamentals_service import FundamentalsService

    class FakeTicker:
        def __init__(self, symbol):
            self.symbol = symbol

        @property
        def info(self):
            return {"sector": "Energy", "trailingPE": 12.1, "marketCap": 5e9,
                    "priceToBook": 0.9, "debtToEquity": 60.0,
                    "ebitdaMargins": 0.22}

    import yfinance as yf
    monkeypatch.setattr(yf, "Ticker", FakeTicker)
    c = _client(tmp_path)
    r = c.get("/fundamentals?symbols=PCG,GM")
    assert r.status_code == 200
    body = r.get_json()
    assert body["PCG"]["sector"] == "Energy"
    assert body["PCG"]["ebitda_margin"] == 22.0


def test_wallet_roundtrip_full_rows(tmp_path):
    """POST tam satirlari (sembol+adet+giris+hedef) saklar; GET geri verir -
    localStorage'in calismadigi durumlarda dashboard buradan kurtarabilir."""
    c = _client(tmp_path)
    payload = {"rows": [{"s": "pcg", "q": 250, "e": 17.82, "t": 19.0},
                        {"s": "AAPL", "q": 10, "e": 220.5, "t": None}]}
    r = c.post("/wallet", json=payload)
    assert r.get_json() == {"ok": True, "count": 2}
    g = c.get("/wallet").get_json()
    assert {"s": "PCG", "q": 250, "e": 17.82, "t": 19.0} in g["rows"]
    assert {"s": "AAPL", "q": 10, "e": 220.5, "t": None} in g["rows"]


def test_wallet_legacy_symbols_format_still_accepted(tmp_path):
    """Eski istemci formati ({symbols:{...}}) hala kabul edilir (uyumluluk)."""
    c = _client(tmp_path)
    r = c.post("/wallet", json={"symbols": {"GM": 5}})
    assert r.get_json()["ok"] is True
    g = c.get("/wallet").get_json()
    assert g["rows"][0]["s"] == "GM" and g["rows"][0]["q"] == 5


def test_handbook_pdf_served(tmp_path):
    """Kullanım kılavuzu PDF'i /kullanici-el-kitabi.pdf ucundan servis edilir."""
    c = _client(tmp_path)
    r = c.get("/kullanici-el-kitabi.pdf")
    assert r.status_code == 200
    assert r.mimetype == "application/pdf"
    assert r.data[:4] == b"%PDF"
    assert len(r.data) > 100_000




def test_data_compare_endpoint_disabled_without_keys(tmp_path):
    """Alpaca anahtari yokken uc zarafetle 'devre disi' der (patlamaz)."""
    c = _client(tmp_path)
    body = c.get("/data-compare").get_json()
    assert body["enabled"] is False




def test_live_rows_expose_signal_and_fill_timestamps():
    """Grafikteki isaretler icin /live satirlari zaman damgalarini ve
    gerekceyi tasimali (aksi halde pano uydurmak zorunda kalir)."""
    from pathlib import Path
    src = Path("app/scheduler.py").read_text()
    for field in ('"signal_ts"', '"fill_ts"', '"entry_reason"', '"created_utc"'):
        assert field in src, field
    tracker = Path("app/services/signal_tracker.py").read_text()
    assert "fill_ts INTEGER" in tracker and "entry_reason" in tracker
    assert "fill_ts=?" in tracker          # dolum ANI kaydediliyor
    assert "def _entry_reason(" in tracker




# ---------------- v4.1 (bybit iskeleti) yapisal testler ----------------
def _tpl() -> str:
    from pathlib import Path
    return Path("app/dashboard.html").read_text(encoding="utf-8")


def test_no_phantom_element_ids():
    """DERS (v3.0): getElementById cagrisinin karsiligi HTML'de yoksa
    script SESSIZCE olur. Iki hayalet id (simSlot, sessBadge) tum panoyu
    oldurmustu; sablon degisti, ders degismedi."""
    import re
    t = _tpl()
    ids = set(re.findall(r'id="([A-Za-z0-9_-]+)"', t))
    called = set(re.findall(r'getElementById\(["\']([A-Za-z0-9_-]+)["\']\)', t))
    # $("x") kisayolu da getElementById'dir
    called |= set(re.findall(r'\$\(["\']([A-Za-z0-9_-]+)["\']\)', t))
    dynamic = {"server-diag"}          # sunucu enjekte ediyor
    missing = called - ids - dynamic
    assert not missing, f"HTML'de karsiligi olmayan id: {sorted(missing)}"


def test_dashboard_only_calls_existing_endpoints():
    """Sablonun cagirdigi her uc sunucuda TANIMLI olmali - bybit
    sablonundan tasinirken /market, /prices, /challengers gibi uclar
    eksik kalirsa pano sessizce bos doner."""
    import re
    from pathlib import Path
    t = _tpl()
    urls = set(re.findall(r'j\(["\`]([^"\`?]+)', t))
    urls |= set(re.findall(r'fetch\(["\`](/[a-z/-]+)', t))
    srv = Path("app/server.py").read_text()
    routes = set(re.findall(r'@app\.(?:get|post)\("([^"]+)"\)', srv))
    for u in urls:
        if "${" in u or not u.startswith("/"):
            continue
        assert u in routes, f"{u} sunucuda yok"


def test_layout_skeleton_matches_bybit_template():
    t = _tpl()
    assert ".app{display:grid" in t                 # 3 satirli kabuk
    assert "grid-template-columns:220px minmax(0,1fr) 300px" in t
    for tab in ("ozet", "sinyaller", "adaylar", "piyasa", "ayar"):
        assert f'data-tab="{tab}"' in t, tab


def test_midas_palette_and_no_crypto_leftovers():
    t = _tpl()
    assert "--bg:#12091F" in t and "--blue:#B18AFF" in t      # mor palet
    low = t.lower()
    for word in ("bybit", "usdt", "parite", "funding"):
        assert word not in low, word


def test_candidates_card_is_exit_lab():
    """ADAYLAR karti = cikis laboratuvari (V0/V1/V2)."""
    t = _tpl()
    for v in ("V0_CANLI", "V1_KISMI", "V2_GENIS"):
        assert v in t, v


def test_server_contract_points_present():
    t = _tpl()
    assert t.count("<!--TAPE-->") == 1
    assert t.count('id="server-diag"') == 0        # sunucu kendisi basar
    assert "edge-cache atlatici" in t
    assert 'id="databand"' in t


def test_new_dashboard_endpoints_return_expected_shapes(tmp_path):
    """v4.1 uyumluluk uclari: canlida 503 dondurmusler cunku
    get_live_status() LISTE dondurur, sozluk degil (zarfi /live rotasi
    kurar). Sekil sozlesmesi burada kilitlenir."""
    tracker = SignalTracker(Database(str(tmp_path / "t.db")), "1h")
    c = _client(tmp_path, tracker=tracker)
    r = c.get("/prices")
    assert r.status_code == 200 and "prices" in r.get_json()
    r = c.get("/market")
    assert r.status_code == 200
    m = r.get_json()
    for k in ("majors", "breadth", "gainers", "losers", "liquid_universe"):
        assert k in m, k


def test_app_grid_children_do_not_break_layout():
    """v4.1.2 REGRESYON: .app{grid-template-rows:56px 1fr 24px} tam uc
    AKIS ICI cocuk bekler. TAPE + databand grid icine konunca ortuk
    satirlar acildi ve tum yerlesim coktu (baslik ortada, KPI dipte).
    Durum bandi artik .app DISINDA (#statusband) yasar."""
    import re
    t = _tpl()
    assert '<div id="statusband">' in t
    # statusband, .app'ten ONCE gelmeli
    assert t.index('id="statusband"') < t.index('class="app"')
    # TAPE ve databand statusband icinde olmali (grid disi)
    sb = t[t.index('id="statusband"'):t.index('class="app"')]
    assert "<!--TAPE-->" in sb and 'id="databand"' in sb
    # .app icinde akis-ici fazladan div OLMAMALI: header'dan once eleman yok
    app_start = t.index('<div class="app">')
    between = t[app_start:t.index("<header", app_start)]
    assert not re.search(r"<div(?![^>]*class=\"app\")", between), between
    # .app yuksekligi banda yer birakir
    assert "height:calc(100vh - 28px)" in t
