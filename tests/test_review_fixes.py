"""v4.22: 7 Agu derin denetim duzeltmeleri - once KIRMIZI yazilan testler.

Bes bagimsiz denetcinin (motor/defter/orkestra/servis/finans) dogrulanmis
bulgulari. Her test once ESKI kodda kirildi (4.1/3 kaniti), sonra duzeltildi.
Kapsam: golge muhasebe (gap sirasi, dolum bari, time-stop capasi), go-live
olcumleri (kume kaliciligi, net-DD), exit_lab kablolamasi, bilanco tazeligi,
denetim damgasi, gist restore damgasi, alarm gurultusu.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from app.services.database import Database
from app.services.signal_tracker import SignalTracker

ROOT = Path(__file__).resolve().parents[1]


def _tracker(tmp_path, **kw):
    db = Database(str(tmp_path / "t.db"))
    return db, SignalTracker(db, "1h", **kw)


def _seed_signal(db, symbol="AAPL", direction="LONG", entry_min=100.0,
                 entry_max=101.0, stop=98.0, tp1=104.0, fill_price=None,
                 fill_ts=None, status="PENDING"):
    db.execute(
        "INSERT INTO signals(symbol,direction,created_utc,entry_candle_ts,"
        "entry_min,entry_max,stop_loss,tp1,tp2,rr,time_stop_date,status,"
        "fill_price,fill_ts,cluster_id,engine_sha) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (symbol, direction, "2026-08-07T14:00:00Z", 1000,
         entry_min, entry_max, stop, tp1, 108.0, 2.5, "2026-08-13",
         status, fill_price, fill_ts, f"{direction}-2026-08-07", "abc123"))
    return db.query_one("SELECT id FROM signals ORDER BY id DESC LIMIT 1")["id"]


def _candle(ts, o, h, l, c, v=1000.0):
    return {"ts": ts, "open": o, "high": h, "low": l, "close": c, "volume": v}


def _insert_candles(db, symbol, candles):
    db.executemany(
        "INSERT OR IGNORE INTO candles(symbol,interval,ts,open,high,low,"
        "close,volume) VALUES(?,?,?,?,?,?,?,?)",
        [(symbol, "1h", c["ts"], c["open"], c["high"], c["low"], c["close"],
          c["volume"]) for c in candles])


# ---------------------------------------------------------------- gap sirasi
def test_gap_through_stop_ayni_barda_tp_gorse_de_loss(tmp_path):
    """Acilis stop OTESINDEYSE sira bilinir: cikis ACILISTAN (yazili kural).
    Eski kod hit_stop+hit_tp'yi gap'ten ONCE kontrol edip AMBIGUOUS(0R)
    yaziyordu - en kotu gap zararlari defterden dusuyordu."""
    db, tr = _tracker(tmp_path)
    _seed_signal(db, fill_price=101.0, fill_ts=2000, status="FILLED")
    # gap-down acilis 96 (stop 98 otesi), gun ici 104.5'e toparlanma (tp1 ustu)
    _insert_candles(db, "AAPL", [_candle(3000, 96.0, 104.5, 95.5, 104.0)])
    tr.evaluate_open("AAPL")
    row = db.query_one("SELECT * FROM signals")
    assert row["outcome"] == "LOSS"
    assert row["exit_price"] == 96.0                    # ACILISTAN
    assert abs(row["r_multiple"] - (96.0 - 101.0) / 3.0) < 0.01   # ~-1.67R


def test_gap_through_tp_ayni_barda_stop_gorse_de_win(tmp_path):
    db, tr = _tracker(tmp_path)
    _seed_signal(db, fill_price=101.0, fill_ts=2000, status="FILLED")
    # gap-up acilis 105 (tp1 104 otesi), gun ici 97'ye cokus (stop alti)
    _insert_candles(db, "AAPL", [_candle(3000, 105.0, 105.5, 97.0, 98.0)])
    tr.evaluate_open("AAPL")
    row = db.query_one("SELECT * FROM signals")
    assert row["outcome"] == "WIN"
    assert row["exit_price"] == 105.0


def test_iki_seviye_arasi_acilista_ambiguous_korunur(tmp_path):
    """Acilis seviyeler ARASINDAYSA sira bilinemez - AMBIGUOUS dogru."""
    db, tr = _tracker(tmp_path)
    _seed_signal(db, fill_price=101.0, fill_ts=2000, status="FILLED")
    _insert_candles(db, "AAPL", [_candle(3000, 100.0, 104.5, 97.5, 100.0)])
    tr.evaluate_open("AAPL")
    row = db.query_one("SELECT * FROM signals")
    assert row["outcome"] == "AMBIGUOUS"


# ------------------------------------------------------------- dolum bari
def test_dolum_barinda_stop_kesilirse_loss(tmp_path):
    """Bolgeyi katedip AYNI barda stop'u da kesen mum zarar yazmali.
    Eski kod dolum barinda 'continue' ile cikis kontrolunu atliyordu."""
    db, tr = _tracker(tmp_path)
    _seed_signal(db)                                    # PENDING
    # tek bar: bolgeye girip (low<=100) stop'u da kesiyor (low<=98)
    _insert_candles(db, "AAPL", [_candle(3000, 102.0, 102.5, 97.5, 99.0)])
    tr.evaluate_open("AAPL")
    row = db.query_one("SELECT * FROM signals")
    assert row["status"] == "CLOSED"
    assert row["outcome"] == "LOSS"
    assert row["fill_price"] == 101.0                   # kotu uc (entry_max)
    assert row["exit_price"] == 98.0                    # stop (gap yok)


def test_dolum_barinda_yalniz_tp_pozisyonu_kapatmaz(tmp_path):
    """Dolum barinda TP'nin dolumdan once mi sonra mi kesildigi bilinemez;
    iyimser WIN yazilmaz, pozisyon acik kalir (kotumser muhasebe)."""
    db, tr = _tracker(tmp_path)
    _seed_signal(db)
    _insert_candles(db, "AAPL", [_candle(3000, 102.0, 104.5, 99.5, 104.0)])
    tr.evaluate_open("AAPL")
    row = db.query_one("SELECT * FROM signals")
    assert row["status"] == "FILLED"                    # kapanmadi
    assert row["outcome"] is None


# ---------------------------------------------------------- time-stop capasi
def test_time_stop_restart_sonrasi_fill_ts_ile_sayar(tmp_path):
    """Coklu-tur degerlendirmede bars_held dolumdan sayilmali. Eski kod
    filled_at_idx'i yalniz dolumun goruldugu turda biliyordu; restart
    sonrasi sayac DOGUMDAN baslayip time-stop'u erken tetikliyordu."""
    db, tr = _tracker(tmp_path, max_track_bars=28)
    # dolum 10. mumda gerceklesmis (fill_ts=11000), restart taklidi:
    # filled_at_idx bellekte YOK, yalniz DB'deki fill_ts var
    _seed_signal(db, fill_price=101.0, fill_ts=11000, status="FILLED")
    # dolumdan sonra 27 sakin mum (seviye kesilmiyor) -> 28 bar DOLMADI
    candles = [_candle(1000 + i * 1000, 101.0, 102.0, 100.5, 101.5)
               for i in range(1, 40)]                   # ts 2000..40000
    _insert_candles(db, "AAPL", candles)
    tr.evaluate_open("AAPL")
    row = db.query_one("SELECT * FROM signals")
    # dolum ts=11000 (10. mum) -> 40000'e kadar 29 bar gecti -> EXPIRED
    # dogru; ama esas olcum: erken EXPIRED OLMAMALI. 11000+27 bar = 38000'de
    # heniz 27 bar -> once o pencereyi dogrula:
    db2 = Database(str(tmp_path / "u.db"))
    tr2 = SignalTracker(db2, "1h", max_track_bars=28)
    _seed_signal(db2, fill_price=101.0, fill_ts=11000, status="FILLED")
    _insert_candles(db2, "AAPL",
                    [c for c in candles if c["ts"] <= 38000])
    tr2.evaluate_open("AAPL")
    r2 = db2.query_one("SELECT * FROM signals")
    assert r2["status"] == "FILLED", (
        f"erken EXPIRED: dolumdan 27 bar gecmisken kapandi ({r2['outcome']})")
    assert row["outcome"] == "EXPIRED"                  # 29 barda dogru kapanis


# ------------------------------------------------------------- net-R DD
def test_max_drawdown_net_r_uzerinden(tmp_path):
    """Go-live beklentisi NET-R ile olculurken DD brut egriden geliyordu;
    net DD her zaman daha derin - 8R esigi iyimser kaciyordu."""
    db, tr = _tracker(tmp_path)
    for i, r in enumerate([-1.0, -1.0, -1.0]):
        db.execute(
            "INSERT INTO signals(symbol,direction,created_utc,entry_min,"
            "entry_max,stop_loss,tp1,status,outcome,fill_price,r_multiple,"
            "closed_utc,blocked) VALUES('S%d','LONG','2026-08-01T00:00:00Z',"
            "100,101,98,104,'CLOSED','LOSS',101,?, '2026-08-0%dT00:00:00Z',0)"
            % (i, i + 1), (r,))
    dd = tr.max_drawdown_r()
    # brut DD=3.0; net DD = 3.0 + 3 islem maliyeti (>0) olmali
    assert dd > 3.0, f"DD brut egriden hesaplanmis: {dd}"


# ------------------------------------------------- yedek/restore butunlugu
def test_export_import_kume_ve_etiketleri_korur(tmp_path):
    db, tr = _tracker(tmp_path)
    db.execute(
        "INSERT INTO signals(symbol,direction,created_utc,entry_min,entry_max,"
        "stop_loss,tp1,status,outcome,fill_price,r_multiple,closed_utc,blocked,"
        "cluster_id,engine_sha,mom_pct,atr_pct,atr_rank,fill_ts,entry_reason,"
        "smc_tags,contract_json) VALUES('AAPL','LONG','2026-08-07T14:00:00Z',"
        "100,101,98,104,'CLOSED','WIN',101,1.5,'2026-08-07T20:00:00Z',0,"
        "'LONG-2026-08-07','abc123',0.91,3.2,0.7,2000,'sebep','[\"tag\"]',"
        "'{\"phase\":\"MORNING\"}')")
    rows = tr.export_signals(500)
    assert rows and rows[0]["cluster_id"] == "LONG-2026-08-07"
    assert rows[0]["engine_sha"] == "abc123"
    assert rows[0]["contract_json"]
    db2 = Database(str(tmp_path / "b.db"))
    tr2 = SignalTracker(db2, "1h")
    assert tr2.import_signals(rows) == 1
    r = db2.query_one("SELECT * FROM signals")
    assert r["cluster_id"] == "LONG-2026-08-07"
    assert r["engine_sha"] == "abc123"
    assert r["mom_pct"] == 0.91 and r["atr_rank"] == 0.7
    assert r["fill_ts"] == 2000
    assert json.loads(r["contract_json"])["phase"] == "MORNING"
    # kume istatistigi restore sonrasi da calisiyor
    cs = tr2.cluster_stats()
    assert cs["clusters"] == 1


# ------------------------------------------------------ exit_lab kablolama
def test_exit_lab_uretimde_canli_fill_window_ile_kurulur():
    """main.py, ExitLab'i settings.FILL_WINDOW_BARS ile kurmali. Eski kod
    varsayilan 12 ile kuruyordu (canli 14) - varyant kiyasi farkli
    orneklem uzerinde yapiliyordu."""
    src = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    assert "fill_window=settings.FILL_WINDOW_BARS" in src


# ------------------------------------------------------ bilanco tazeligi
def test_earnings_ready_bayatlayinca_fail_closed(tmp_path):
    from app.services.earnings_service import EarningsService
    from app.services.market_calendar import MarketCalendar
    from datetime import date

    class _FH:
        def get_earnings_calendar(self, a, b):
            return [{"symbol": "AAPL", "date": "2026-08-20"}]

    svc = EarningsService(_FH(), MarketCalendar())
    svc.refresh(date(2026, 8, 7))
    assert svc.status()["ready"] is True
    # 25 saat oncesine cek: veri BAYAT -> ready dusmeli, info fail-closed
    svc._last_ok = time.time() - 25 * 3600
    assert svc.status()["ready"] is False
    info = svc.info("AAPL", date(2026, 8, 7))
    assert info.available is False


# ------------------------------------------------------ denetim damgasi
def test_audit_bilanco_korumasi_dogum_ani_damgasiyla(tmp_path):
    """Kontrol 'su an ready mi' degil 'sinyal dogarken ready miydi'
    sorusuna bakmali. Eski kontrol gun-ici restart'ta yanlis pozitif,
    gun sonu toparlanmada yanlis negatif veriyordu."""
    from app.services.self_audit import run_audit
    db, tr = _tracker(tmp_path)
    # takvim HAZIRKEN dogmus bugunku sinyal (damga true)
    db.execute(
        "INSERT INTO signals(symbol,direction,created_utc,status,blocked,"
        "contract_json) VALUES('AAPL','LONG',?, 'PENDING',0,"
        "'{\"earnings_ready\": true}')", (time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),))

    class _E:
        def status(self):
            return {"ready": False, "symbols": 0, "fail_streak": 0,
                    "last_ok_age_min": None}

    rep = run_audit(db, earnings=_E())
    chk = next(c for c in rep.checks if c.name == "bilanco korumasi")
    assert chk.ok, f"yanlis pozitif: {chk.detail}"
    # takvim KAPALIYKEN dogmus sinyal (damga false) -> gercek ihlal
    db.execute(
        "INSERT INTO signals(symbol,direction,created_utc,status,blocked,"
        "contract_json) VALUES('MSFT','LONG',?, 'PENDING',0,"
        "'{\"earnings_ready\": false}')", (time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),))
    rep2 = run_audit(db, earnings=_E())
    chk2 = next(c for c in rep2.checks if c.name == "bilanco korumasi")
    assert not chk2.ok


# ------------------------------------------------------ gist restore damgasi
def test_restore_meta_damgasini_tasir(tmp_path):
    from app.services.gist_backup import GistBackup

    class _C:
        def find_gist(self, *a):
            return "g1"

        def fetch_gist(self, gid):
            return {"0_meta.json": json.dumps(
                {"synced_utc": "2026-08-07T12:00:00Z"})}

        def gist_url(self, gid):
            return "u"

    db, tr = _tracker(tmp_path)
    b = GistBackup(_C(), tr, pinned_gist_id="g1")
    assert b.restore_if_empty() is True
    assert b.info()["last_sync_utc"] == "2026-08-07T12:00:00Z"


# ------------------------------------------------------ alarm gurultusu
def test_news_sessiz_tur_backoff_tetiklemez():
    from app.services.news_service import NewsService
    svc = NewsService.__new__(NewsService)
    svc._interval = 0.0
    svc._backoff = 0.0
    svc._last = 0.0
    svc._slow_sec = 30.0
    svc.refresh = lambda symbols, today: 0     # hizli ve sifir yeni haber
    svc.maybe_refresh(["AAPL"], None)
    assert svc._backoff == 0.0, "added==0 sagliklidir, backoff tetiklenmemeli"


def test_finnhub_timeout_devre_kesiciyi_acar():
    import requests
    from app.integrations.finnhub_client import FinnhubClient
    fc = FinnhubClient("k")

    class _S:
        def get(self, *a, **k):
            raise requests.ConnectTimeout("boom")

    fc._session = _S()
    for _ in range(10):
        fc._get("/quote", {"symbol": "AAPL"})
    assert fc._fail_count >= 1
    assert fc._blocked_until > time.time(), "timeout breaker'i acmali"
