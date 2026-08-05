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
    # v4.1.8: acik tema RENK KALINTILARI (krem zebra, linen ipucu kutusu)
    for leftover in ("rgba(249,245,236", "#2A241B", "#FFFEFA", "#8A7F6C",
                     "#B9B29F", "#FBF8F2"):
        assert leftover not in t, leftover
    low = t.lower()
    for word in ("bybit", "usdt", "parite", "funding"):
        assert word not in low, word
    # mobil medya blogu paleti ACIK temaya cevirmemeli (v4.1.3 vakasi:
    # bybit mobilde --bg:#F6F4FB'ye donuyordu, mobil bembeyaz acildi)
    assert "--bg:#F6F4FB" not in t and "--card:#FFFFFF" not in t
    assert "rgba(255,255,255,.97)" not in t


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
    # v4.1.6: viewport kilidi KALKTI - kartlar icerigi kadar uzar,
    # sayfa kayar (sikisik mini-scroll kutulari yok)
    assert "min-height:100vh;gap:10px" in t
    assert "height:calc(100vh - 28px)" not in t
    assert ".cols > .col{overflow:visible" in t


def test_template_uses_midas_field_names_not_bybit():
    """v4.1.5 VAKASI: sablon bybit alan adlarini okuyordu ->
    tabloda 'undefined', haberlerde 'undefined', grafik bos.
    Bybit'e ozgu alan adlari sablonda BULUNMAMALI."""
    t = _tpl()
    for bad in (".pair", "it.title}", "published_utc}"):
        assert bad not in t, bad
    assert "s.symbol" in t                      # sinyal sembolu
    assert "it.headline" in t                   # haber basligi
    assert "it.datetime" in t                   # haber zamani


def test_signal_fields_read_by_template_exist_in_api(tmp_path):
    """Sablonun okudugu sinyal alanlari /signals ciktisinda GERCEKTEN
    var mi? (undefined sutunlarin kok nedeni buydu.)"""
    import re
    from app.services.signal_tracker import SignalTracker as _ST
    t = _tpl()
    read = set(re.findall(r"\bs\.([a-z_]+)\b", t))
    tracker = _ST(Database(str(tmp_path / "t.db")), "1h")
    cols = {r["name"] for r in tracker._db.query("PRAGMA table_info(signals)")}
    extra = {"symbol", "status", "outcome"}      # sorguda adi ayni
    js_builtins = {"length", "map", "push", "filter", "slice", "join",
                   "sort", "find", "forEach", "indexOf", "reduce", "some",
                   "toFixed", "replace", "split", "concat", "includes",
                   "tp", "value", "textContent", "style", "id"}
    unknown = read - cols - extra - js_builtins
    # kalanlar sablonun kendi turettigi alanlar olabilir; kritik olanlar:
    for f in ("symbol", "direction", "entry_min", "entry_max", "stop_loss",
              "tp1", "fill_price", "r_multiple", "confidence", "setup_type"):
        assert f in cols, f
    assert "pair" not in read, "bybit alan adi kalmis"


def test_candidates_column_visible_on_desktop():
    """ADAYLAR (cikis laboratuvari) bybit'te YALNIZ mobil sekmede
    gorunuyordu; bizde masaustunde de gorunmeli."""
    t = _tpl()
    # v4.1.6: kart SAG SUTUNDA gercek bir kart (display:contents grid'e
    # 4. sutun sokuyor ve piyasa nabzini asagi itiyordu)
    assert '<div class="card fill" data-tab="adaylar">' in t
    assert 'display:contents}' not in t     # kural olarak yok (yorumda gecebilir)


def test_detail_card_shows_company_data():
    t = _tpl()
    assert "/fundamentals?symbols=" in t
    assert "FAVÖK marjı" in t and "Sektör / Sanayi" in t


def test_dashboard_renders_with_real_payloads():
    """DUMAN TESTI: pano GERCEK API yanitlariyla jsdom'da calistirilir.
    'Sinyal tablosu bos, ekran siyah' vakasinin tekrarini engeller -
    sablon yuklenip 19 satir cizemezse test kirilir.
    node+jsdom yoksa atlanir (CI'da opsiyonel)."""
    import json
    import shutil
    import subprocess
    import tempfile
    from pathlib import Path

    import pytest
    if not shutil.which("node"):
        pytest.skip("node yok")
    check = subprocess.run(["node", "-e", "require('jsdom')"],
                           capture_output=True, cwd="/tmp")
    if check.returncode != 0:
        pytest.skip("jsdom yok")

    fix = Path(tempfile.mkdtemp())
    sig = [{"id": i, "symbol": "AAPL", "direction": "LONG",
            "status": "CLOSED", "outcome": "WIN", "created_utc":
            "2026-08-03T13:30:00Z", "entry_min": 100, "entry_max": 101,
            "stop_loss": 98, "tp1": 104, "tp2": 107, "rr": 2.0,
            "fill_price": 101, "r_multiple": 1.0, "confidence": "HIGH",
            "setup_type": "breakout_retest"} for i in range(1, 20)]
    (fix / "api_signals_limit_500.json").write_text(json.dumps(sig))
    (fix / "api_performance.json").write_text(json.dumps(
        {"decided_trades": 19, "win_rate": 0.5, "total_r_multiple": 1.0,
         "open_signals": 0, "closed_by_outcome": {}, "by_direction": {},
         "net": {}, "phases": {}}))
    for name, body in (("api_status.json", {"meta": {}, "results": {}}),
                       ("api_universe.json", {"filtered_count": 300,
                                              "raw_count": 1637}),
                       ("api_news.json", {"items": []}),
                       ("api_challengers.json", {"strategies": {}}),
                       ("api_market.json", {"majors": []}),
                       ("api_prices.json", {"prices": {}}),
                       ("api_live.json", {"rows": [], "indices": []}),
                       ("api_strategy_lab.json", {"pending": True})):
        (fix / name).write_text(json.dumps(body))

    script = str(Path("tools/dashboard_smoke.js").resolve())
    out = subprocess.run(["node", script],
                         capture_output=True, text=True, timeout=120,
                         cwd="/tmp",
                         env={"PATH": "/usr/bin:/bin",
                              "NODE_PATH": "/tmp/node_modules",
                              "DASH": str(Path("app/dashboard.html").resolve()),
                              "FIXDIR": str(fix) + "/"})
    assert "SMOKE_OK" in out.stdout, out.stdout + out.stderr


def test_detail_shows_why_the_signal_fired():
    """v4.1.7: 'hangi veriye gore sinyal geldi' detayda GORUNMELI.
    entry_reason sinyal dogarken yazilir; momentum/SMC etiketleri
    ayrica ve ACIKCA 'karara girmez' notuyla gosterilir."""
    t = _tpl()
    assert "NEDEN BU SİNYAL" in t
    assert "s.entry_reason" in t
    # kayit yoksa BOS BIRAKMA: durustce soyle + plan verisinden ozet
    assert "kayıtlı gerekçe yok" in t
    assert "s.mom_pct" in t and "smc_tags" in t
    assert "karara girmez" in t


def test_strategy_lab_layer_present():
    """KATMAN 2: bagimsiz aday GIRIS stratejileri panoda gorunmeli;
    tarihsel degerler BACKTEST olarak ETIKETLENMELI."""
    t = _tpl()
    assert "/strategy-lab" in t
    assert "renderStrategyLab" in t and 'id="slabBody"' in t
    assert "kohort · tavansız" in t and "kohort · tavanlı" in t
    assert "canlı kanıt değildir" in t


def test_strategy_card_reflects_our_engine_not_bybit():
    """v4.2: strateji karti bybit'in SABIT metnini gosteriyordu
    (BTC 4H rejimi, 4H->15m, retest·sweep) - bizim motorumuzla ilgisi
    yoktu. Artik midas gercegi + canli ayarlardan doldurulan alanlar."""
    t = _tpl()
    assert "BTC" not in t
    assert "SPY + QQQ rejimi" in t
    assert "1G → 1S" in t
    for el in ("stratRR", "stratVol", "stratEarn", "stratHold", "stratUni"):
        assert f'id="{el}"' in t, el
    assert "cfg.risk_reward_min" in t and "cfg.time_stop_days" in t


def test_status_exposes_engine_config(tmp_path):
    """Strateji karti canli ayarlardan beslenebilmeli."""
    c = _client(tmp_path)
    meta = c.get("/status").get_json()["meta"]
    for k in ("risk_reward_min", "volume_mult", "earnings_blackout_days",
              "time_stop_days", "max_daily_signals", "max_open_signals"):
        assert k in meta, k


def test_keyboard_shortcuts_do_not_hijack_typing():
    """v4.3: 1-5 sekme, R yenile, ? yardim. Girdi alanindayken veya
    modifier basiliyken DEVREYE GIRMEMELI - aksi halde hesaplayiciya
    rakam yazmak sekme degistirir."""
    t = _tpl()
    assert "const KEY_TABS=" in t
    assert "function inInput(t)" in t
    assert "if(inInput(e.target)||e.ctrlKey||e.metaKey||e.altKey) return;" in t
    assert 'id="keyhelp"' in t          # yardim katmani gercek eleman


def test_volatility_card_present():
    t = _tpl()
    assert "/volatility" in t and "renderVolatility" in t
    assert 'id="volBody"' in t


def test_volatility_endpoint_shape(tmp_path):
    """Gunluk veri yokken 'pending' doner, patlamaz."""
    c = _client(tmp_path)
    r = c.get("/volatility")
    assert r.status_code == 200
    body = r.get_json()
    assert body.get("pending") is True or "median" in body


def test_atr_measurement_recorded_and_shown():
    """v4.6: 'oynak hisselerdeki sinyaller daha mi iyiydi' sorusunu
    kohort dolunca cevaplayabilmek icin ATR yuzdesi ve evren dilimi
    sinyal DOGARKEN kaydedilir. SALT OLCUM - karara karismaz."""
    from pathlib import Path
    tr = Path("app/services/signal_tracker.py").read_text()
    assert '"atr_pct REAL", "atr_rank REAL"' in tr
    sched = Path("app/scheduler.py").read_text()
    assert "def _atr_pcts(self, daily: dict)" in sched
    assert "atr_pct=_ap[0], atr_rank=_ap[1]" in sched
    assert '"atr_pct": sig.get("atr_pct")' in sched
    t = _tpl()
    assert "s.atr_pct" in t and "s.atr_rank" in t
    assert "oynaklık: ATR" in t
    # karar modulleri ATR SIRALAMASINI kullanmamali (yalniz olcum)
    eng = Path("app/strategies/signal_engine.py").read_text()
    assert "atr_rank" not in eng


def test_candidates_visible_on_mobile_tab():
    """v4.14 VAKASI: mobilde 'Adaylar' sekmesine dokununca HICBIR SEY
    gorunmuyordu. Sebep: mobilde yalniz aktif SUTUN gorunur, aday karti
    ise Piyasa sutununun ICINDE yasiyor - kart .on olsa bile ustundeki
    sutun gizliydi. jsdom'da CSS gercekten uygulanarak dogrulanir."""
    import shutil
    import subprocess
    from pathlib import Path

    import pytest
    if not shutil.which("node"):
        pytest.skip("node yok")
    if subprocess.run(["node", "-e", "require('jsdom')"],
                      capture_output=True, cwd="/tmp").returncode != 0:
        pytest.skip("jsdom yok")

    out = subprocess.run(
        ["node", str(Path("tools/mobile_tab_visibility.js").resolve())],
        capture_output=True, text=True, timeout=90, cwd="/tmp",
        env={"PATH": "/usr/bin:/bin", "NODE_PATH": "/tmp/node_modules",
             "DASH": str(Path("app/dashboard.html").resolve())})
    assert "VIS_OK" in out.stdout, out.stdout + out.stderr
