"""v4.54 TEMA RADARI - davranis testleri.

Kilitlenenler:
- Siralama/bilesik RS matematigi (bagimsiz elle hesapla karsilastirilir)
- ISINIYOR'un her sarti TASIYICI: sart bozulunca isaret DUSER
  (yalniz "gecti" senaryosu kontrolun calistigini kanitlamaz - 4.1/3)
- SOGUYOR durum makinesi + testere freni (cooldown)
- Fail-closed: SPY yok / bayat / eksik gunlu / yetersiz -> isaret yok,
  kesinti basina TEK uyari (2.1/2.2, alarm gurultusu dersi)
- Haftalik rapor ISO haftasinda bir kez; durum restart'i atlatir
- Izolasyon: karar modulleri radari import etmez, tarama yolu okumaz (2.4)
- Kanal: golge mod (TELEGRAM_ENABLED=false) radari susturmaz; radarin
  kendi bayragi susturur
Testler duvar saatinden bagimsizdir: 'bugun' her yerde enjekte edilir.
"""
from __future__ import annotations

import ast
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.models.candle import Candle, KlineSeries
from app.scheduler import Scheduler
from app.services.database import Database
from app.services.theme_radar import (RadarParams, ThemeRadar, compute_report,
                                      evaluate_signals, parse_universe)

ROOT = Path(__file__).resolve().parents[1]
ET = ZoneInfo("America/New_York")

N = 200
D_END = date(2026, 10, 23)          # Cuma - son kapanis
TODAY = date(2026, 10, 26)          # Pazartesi - radar kosumu
SPEC = ("HOT:Sicak,SUPER:Super,MID:Orta,W1:Zayif1,W2:Zayif2,W3:Zayif3")


# ------------------------------------------------------------- veri kurucu
def _bdays(n: int, end: date) -> list[date]:
    out, d = [], end
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d -= timedelta(days=1)
    return out[::-1]


def _path(early: float, late: float, late_n: int = 60,
          start: float = 100.0) -> list[float]:
    closes, p = [], start
    for i in range(N):
        p *= 1 + (late if i >= N - late_n else early)
        closes.append(p)
    return closes


def _vols(late_mult: float = 1.0, late_n: int = 10) -> list[float]:
    return [1_000_000 * (late_mult if i >= N - late_n else 1.0)
            for i in range(N)]


def _series(sym: str, closes, vols, dates) -> KlineSeries:
    return KlineSeries(symbol=sym, interval="1d", candles=[
        Candle(ts=int(datetime(d.year, d.month, d.day,
                               tzinfo=timezone.utc).timestamp() * 1000),
               open=c, high=c, low=c, close=c, volume=v)
        for d, c, v in zip(dates, closes, vols)])


def _market(end: date = D_END, hot_vol: float = 2.0,
            hot_closes=None) -> dict:
    dates = _bdays(N, end)
    paths = {
        "SPY": (_path(0.0003, 0.0003), _vols()),
        "HOT": (hot_closes or _path(0.0, 0.01), _vols(hot_vol)),
        "SUPER": (_path(0.0, 0.015), _vols()),     # en guclu ama hacim duz
        "MID": (_path(0.0005, 0.002), _vols()),
        "W1": (_path(0.0002, -0.002), _vols()),
        "W2": (_path(0.0002, -0.003), _vols()),
        "W3": (_path(0.0002, -0.004), _vols()),
    }
    return {s: _series(s, c, v, dates) for s, (c, v) in paths.items()}


UNI = parse_universe(SPEC)


# --------------------------------------------------------------- hesap
def test_siralama_ve_bilesik_rs_elle_hesapla_ayni():
    rep = compute_report(_market(), UNI, TODAY)
    assert rep["status"] == "ok" and rep["asof"] == D_END.isoformat()
    order = [r["symbol"] for r in rep["rows"]]
    assert order == ["SUPER", "HOT", "MID", "W1", "W2", "W3"]

    hot = next(r for r in rep["rows"] if r["symbol"] == "HOT")
    c, b = _path(0.0, 0.01), _path(0.0003, 0.0003)

    def rs(n):
        return (c[-1] / c[-1 - n] - (b[-1] / b[-1 - n])) * 100

    assert abs(hot["rs20"] - rs(20)) < 0.01
    assert abs(hot["rs60"] - rs(60)) < 0.01
    assert abs(hot["rs120"] - rs(120)) < 0.01
    expect = 0.5 * rs(20) + 0.3 * rs(60) + 0.2 * rs(120)
    assert abs(hot["composite"] - expect) < 0.02
    # hacim: son 10 gun 2M, son 50 gun ort (40x1M + 10x2M)/50 = 1.2M
    assert hot["vol_ratio"] == round(2.0 / 1.2, 2)
    assert hot["rs_line_high"] and hot["above_ma50"]


def test_isiniyor_hacim_sarti_tasiyici():
    """Ayni veri, tek fark hacim: hacim artisi yoksa isaret DUSER."""
    p = RadarParams()
    ev, _ = evaluate_signals(compute_report(_market(), UNI, TODAY, p),
                             {}, p, TODAY)
    assert [(e["type"], e["row"]["symbol"]) for e in ev] == [("heating", "HOT")]

    flat = compute_report(_market(hot_vol=1.0), UNI, TODAY, p)
    ev2, st2 = evaluate_signals(flat, {}, p, TODAY)
    assert ev2 == [] and st2["hot"] == {}


def test_isiniyor_siralama_sarti_tasiyici():
    """HOT 2. sirada: TOP_N=1 iken isaret yok, TOP_N=3 iken var.
    SUPER birinci ama hacmi duz -> hicbir N'de isaret almaz."""
    rep = compute_report(_market(), UNI, TODAY)
    ev1, _ = evaluate_signals(rep, {}, RadarParams(top_n=1), TODAY)
    assert ev1 == []
    ev3, _ = evaluate_signals(rep, {}, RadarParams(top_n=3), TODAY)
    assert [e["row"]["symbol"] for e in ev3] == ["HOT"]


def test_isiniyor_ma50_ve_rs_zirve_sarti_tasiyici():
    """HOT once kosup sonra geri cekildi: RS cizgisi zirvede DEGIL ve
    fiyat MA50 altinda -> hacim artsa da isaret yok."""
    closes = _path(0.0, 0.01, late_n=60)
    closes = closes[:-8] + [closes[-9] * (0.97 ** k) for k in range(1, 9)]
    rep = compute_report(_market(hot_closes=closes), UNI, TODAY)
    hot = next(r for r in rep["rows"] if r["symbol"] == "HOT")
    assert hot["rs_line_high"] is False
    ev, _ = evaluate_signals(rep, {}, RadarParams(), TODAY)
    assert ev == []


# --------------------------------------------------- durum makinesi
def _rep(rows, status="ok"):
    return {"status": status, "rows": rows}


def _row(sym="URA", rank=1, high=True, ma=True, vol=1.5):
    return {"symbol": sym, "rank": rank, "rs_line_high": high,
            "above_ma50": ma, "vol_ratio": vol}


def test_sicakken_tekrar_yok_soguma_bir_kez_testere_freni():
    p = RadarParams(cooldown_days=14)
    d0 = date(2026, 10, 1)
    ev, st = evaluate_signals(_rep([_row()]), {}, p, d0)
    assert [e["type"] for e in ev] == ["heating"]
    ev, st = evaluate_signals(_rep([_row()]), st, p, d0 + timedelta(days=1))
    assert ev == []                                   # zaten sicak
    ev, st = evaluate_signals(_rep([_row(ma=False)]), st, p,
                              d0 + timedelta(days=2))
    assert [e["type"] for e in ev] == ["cooling"]
    assert ev[0]["since"] == d0.isoformat() and st["hot"] == {}
    ev, st = evaluate_signals(_rep([_row(ma=False)]), st, p,
                              d0 + timedelta(days=3))
    assert ev == []                                   # soguma bir kez
    ev, st = evaluate_signals(_rep([_row()]), st, p, d0 + timedelta(days=5))
    assert ev == []                                   # testere freni
    ev, st = evaluate_signals(_rep([_row()]), st, p, d0 + timedelta(days=14))
    assert [e["type"] for e in ev] == ["heating"]


def test_veri_yok_soguma_degildir_ve_durum_ok_degilse_isaret_yok():
    p = RadarParams()
    d0 = date(2026, 10, 1)
    _, st = evaluate_signals(_rep([_row()]), {}, p, d0)
    ev, st2 = evaluate_signals(_rep([_row("OTHER", vol=1.0)]), st, p,
                               d0 + timedelta(days=1))
    assert ev == [] and "URA" in st2["hot"]          # URA satiri yok
    ev, st3 = evaluate_signals(_rep([_row(ma=False)], status="stale"),
                               st, p, d0 + timedelta(days=2))
    assert ev == [] and st3 == st                     # dokunulmadi


def test_hacim_verisi_yoksa_isaret_yok():
    ev, _ = evaluate_signals(_rep([_row(vol=None)]), {}, RadarParams(),
                             date(2026, 10, 1))
    assert ev == []


# ---------------------------------------------------- fail-closed veri
def test_spy_yoksa_siralama_yok():
    m = _market()
    del m["SPY"]
    rep = compute_report(m, UNI, TODAY)
    assert rep["status"] == "no_benchmark" and rep["rows"] == []


def test_spy_bayatsa_siralama_yok():
    rep = compute_report(_market(), UNI, D_END + timedelta(days=10))
    assert rep["status"] == "stale" and rep["rows"] == []


def test_bayat_etf_siralamaya_girmez():
    m = _market()
    s = m["MID"]
    m["MID"] = KlineSeries(symbol="MID", interval="1d", candles=s.candles[:-1])
    rep = compute_report(m, UNI, TODAY)
    assert "MID" not in [r["symbol"] for r in rep["rows"]]
    miss = {x["symbol"]: x["reason"] for x in rep["missing"]}
    assert miss["MID"].startswith("bayat")


def test_eksik_gunlu_etf_siralamaya_girmez():
    m = _market()
    cs = m["W1"].candles
    m["W1"] = KlineSeries(symbol="W1", interval="1d",
                          candles=cs[:-10] + cs[-7:])   # 3 gun delik
    rep = compute_report(m, UNI, TODAY)
    miss = {x["symbol"]: x["reason"] for x in rep["missing"]}
    assert miss["W1"] == "eksik gun (3)"
    # 2 gunluk delik tolere edilir (tatil/sağlayici kaymasi)
    m2 = _market()
    cs2 = m2["W1"].candles
    m2["W1"] = KlineSeries(symbol="W1", interval="1d",
                           candles=cs2[:-10] + cs2[-8:])
    assert "W1" in [r["symbol"]
                    for r in compute_report(m2, UNI, TODAY)["rows"]]


def test_yetersiz_gecerli_etf_varsa_isaret_yok():
    m = _market()
    for s in ("W1", "W2", "W3"):
        del m[s]
    rep = compute_report(m, UNI, TODAY)
    assert rep["status"] == "insufficient"           # 3/6 < 5
    ev, _ = evaluate_signals(rep, {}, RadarParams(), TODAY)
    assert ev == []                                   # HOT sartlari tutsa da


def test_kesinti_basina_tek_uyari_ve_donus_notu():
    r = ThemeRadar(SPEC)
    m = _market()
    no_spy = {k: v for k, v in m.items() if k != "SPY"}
    msgs = r.run(no_spy, TODAY)
    assert len(msgs) == 1 and "UYARI" in msgs[0] and "SPY" in msgs[0]
    assert r.run(no_spy, TODAY + timedelta(days=1)) == []   # tekrar yok
    msgs = r.run(m, TODAY + timedelta(days=2))
    assert msgs[0].startswith("TEMA RADARI | veri geri geldi")
    assert any(x.startswith("TEMA RADARI - HAFTALIK") for x in msgs)


# ------------------------------------------------- haftalik + kalicilik
def test_haftalik_iso_haftada_bir_kez_ve_siralama_degisimi():
    r = ThemeRadar(SPEC)
    msgs = r.run(_market(), TODAY)
    assert msgs[0].startswith("TEMA RADARI - HAFTALIK")
    assert "ISINAN TEMA: Sicak (HOT)" in msgs[1]
    assert "(=)" not in msgs[0]                       # ilk hafta: kiyas yok
    assert r.run(_market(), TODAY + timedelta(days=1)) == []
    nxt = TODAY + timedelta(days=7)
    msgs = r.run(_market(end=D_END + timedelta(days=7)), nxt)
    assert len(msgs) == 1 and msgs[0].startswith("TEMA RADARI - HAFTALIK")
    assert " 2. HOT Sicak" in msgs[0] and "(=)" in msgs[0]
    assert "Sicak temalar: HOT" in msgs[0]


def test_durum_restarti_atlatir(tmp_path):
    db = Database(str(tmp_path / "bot.db"))
    r1 = ThemeRadar(SPEC, db=db)
    assert len(r1.run(_market(), TODAY)) == 2         # haftalik + isinan
    r2 = ThemeRadar(SPEC, db=db)                      # restart
    assert r2.last_run_date() == TODAY
    assert "HOT" in r2.state["hot"]
    assert r2.run(_market(), TODAY) == []             # tekrar bildirim yok


def test_onizleme_durumu_degistirmez():
    r = ThemeRadar(SPEC)
    out = r.preview(_market(), TODAY)
    assert out["dry"] and out["would_alert"] == [{"type": "heating",
                                                  "symbol": "HOT"}]
    assert r.state == {}


def test_varsayilan_evren_ve_bayraklar():
    from app.config.settings import Settings
    s = Settings(_env_file=None)
    uni = parse_universe(s.THEME_RADAR_ETFS)
    syms = [u[0] for u in uni]
    assert len(syms) == 18 and len(set(syms)) == 18 and "SPY" not in syms
    assert {"URA", "GRID", "BOTZ", "ITA", "UFO", "QTUM", "REMX"} <= set(syms)
    assert s.THEME_RADAR_ENABLED and s.THEME_RADAR_TELEGRAM
    assert parse_universe("spy:x, ura:Uranyum ,URA:tekrar,,GRID") == [
        ("URA", "Uranyum"), ("GRID", "GRID")]


# --------------------------------------------------------- izolasyon
def test_karar_modulleri_radari_import_edemez():
    """IZOLASYON ANAHTARI (anayasa 2.4): radar salt olcum. Karar ureten
    moduller onu import edemez - AST duzeyinde."""
    files = list((ROOT / "app" / "strategies").glob("*.py")) + [
        ROOT / "app" / "services" / "signal_tracker.py",
        ROOT / "app" / "services" / "universe.py",
    ]
    for f in files:
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            assert not any("theme_radar" in n for n in names), \
                f"{f.name} tema radarini import ediyor - izolasyon ihlali"


def test_tarama_yolu_radari_okumaz():
    """Scheduler radari KOSTURUR ama tarama/izleme/dispatch yolu ona
    dokunmaz: bu fonksiyonlarin govdesinde 'radar' gecemez."""
    tree = ast.parse((ROOT / "app" / "scheduler.py").read_text(encoding="utf-8"))
    guarded = {"_run_coarse_scan_locked", "_collect_watch", "_dispatch",
               "run_fine_scan", "_fine_reevaluate", "_entry_block",
               "run_gap_watch"}
    seen = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in guarded:
            seen.add(node.name)
            assert "radar" not in ast.unparse(node), node.name
    assert seen == guarded            # fonksiyon adi degisirse test bilsin


# --------------------------------------------------- scheduler baglantisi
class _Notifier:
    def __init__(self, ok=True):
        self.sent, self.ok, self.configured = [], ok, True

    def send(self, text):
        self.sent.append(text)
        return self.ok


class _MD:
    def __init__(self, daily=None, exc=None):
        self.daily, self.exc, self.calls = daily or {}, exc, []

    def get_daily_bulk(self, symbols, period=None):
        self.calls.append((tuple(symbols), period))
        if self.exc:
            raise self.exc
        return {s: v for s, v in self.daily.items() if s in symbols}


def _sched(md, radar_tg=True, signals_on=False, db=None):
    s = object.__new__(Scheduler)
    s._settings = SimpleNamespace(
        TELEGRAM_ENABLED=signals_on, TELEGRAM_ALERTS_ENABLED=True,
        THEME_RADAR_TELEGRAM=radar_tg, THEME_RADAR_PERIOD="1y")
    s._notifier = _Notifier()
    s._md = md
    s._scan_gate = threading.Lock()
    s._theme_radar = ThemeRadar(SPEC, db=db)
    s._radar_date = None
    s._prep_date = None
    s._radar_sent = s._radar_fail = s._radar_muted = 0
    s._tg_muted = s._tg_fail = 0
    s._tg_last_ok = 0.0
    return s


OPEN = datetime(2026, 10, 26, 9, 30, tzinfo=ET)
CLOSE = datetime(2026, 10, 26, 16, 0, tzinfo=ET)


def test_golge_mod_radari_susturmaz_kendi_bayragi_susturur():
    s = _sched(_MD(), radar_tg=True, signals_on=False)
    assert s._send("SINYAL | AAPL LONG") is False     # golge mod
    assert s._send_radar("TEMA RADARI | x") is True
    assert s._notifier.sent == ["TEMA RADARI | x"]
    s2 = _sched(_MD(), radar_tg=False)
    assert s2._send_radar("TEMA RADARI | x") is False
    assert s2._notifier.sent == [] and s2._radar_muted == 1
    st = s.telegram_status()
    assert st["radar_on"] and st["radar_sent"] == 1 and st["failed"] == 0


def test_zamanlama_hazirliktan_sonra_seans_disinda_gunde_bir():
    md = _MD(_market())
    s = _sched(md)
    pre = datetime(2026, 10, 26, 8, 46, tzinfo=ET)
    s._maybe_theme_radar(pre, TODAY, OPEN, CLOSE)
    assert md.calls == []                             # hazirlik yapilmadi
    s._prep_date = TODAY
    s._maybe_theme_radar(datetime(2026, 10, 26, 10, 0, tzinfo=ET),
                         TODAY, OPEN, CLOSE)
    assert md.calls == []                             # seans ici: kosmaz
    s._maybe_theme_radar(pre, TODAY, OPEN, CLOSE)
    assert len(md.calls) == 1
    assert "SPY" in md.calls[0][0] and md.calls[0][1] == "1y"
    assert len(s._notifier.sent) == 2                 # haftalik + isinan
    s._maybe_theme_radar(pre + timedelta(minutes=5), TODAY, OPEN, CLOSE)
    assert len(md.calls) == 1                         # gunde bir


def test_restart_sonrasi_ayni_gun_tekrar_indirmez(tmp_path):
    db = Database(str(tmp_path / "bot.db"))
    md = _MD(_market())
    s = _sched(md, db=db)
    s._prep_date = TODAY
    s._maybe_theme_radar(datetime(2026, 10, 26, 8, 46, tzinfo=ET),
                         TODAY, OPEN, CLOSE)
    md2 = _MD(_market())
    s2 = _sched(md2, db=db)                           # restart
    s2._prep_date = TODAY
    s2._maybe_theme_radar(datetime(2026, 10, 26, 8, 50, tzinfo=ET),
                          TODAY, OPEN, CLOSE)
    assert md2.calls == [] and s2._notifier.sent == []


def test_indirme_hatasi_tick_dusurmez_tek_uyari_gider():
    s = _sched(_MD(exc=RuntimeError("yahoo down")))
    s._prep_date = TODAY
    s._maybe_theme_radar(datetime(2026, 10, 26, 8, 46, tzinfo=ET),
                         TODAY, OPEN, CLOSE)
    assert len(s._notifier.sent) == 1 and "UYARI" in s._notifier.sent[0]
    assert s._theme_radar.last_report["status"] == "no_benchmark"


class _FlakyMD(_MD):
    """Ilk cagrida 'drop' sembollerini dusurur (27 Eki GRID rate-limit
    vakasi); sonraki cagrilarda 'still' disindakileri verir."""

    def __init__(self, daily, drop, still=()):
        super().__init__(daily)
        self.drop, self.still = set(drop), set(still)

    def get_daily_bulk(self, symbols, period=None):
        out = super().get_daily_bulk(symbols, period)
        skip = self.drop if len(self.calls) == 1 else self.still
        return {s: v for s, v in out.items() if s not in skip}


def test_eksik_sembol_icin_tek_tekrar():
    md = _FlakyMD(_market(), drop={"MID", "W2"})
    s = _sched(md)
    s._RADAR_RETRY_WAIT_SEC = 0
    s.run_theme_radar(TODAY, send=False)
    assert len(md.calls) == 2 and set(md.calls[1][0]) == {"MID", "W2"}
    rep = s._theme_radar.last_report
    assert rep["missing"] == [] and len(rep["rows"]) == 6

    md2 = _FlakyMD(_market(), drop={"MID"}, still={"MID"})
    s2 = _sched(md2)
    s2._RADAR_RETRY_WAIT_SEC = 0
    s2.run_theme_radar(TODAY, send=False)
    assert len(md2.calls) == 2                        # TEK tekrar, dongu yok
    miss = s2._theme_radar.last_report["missing"]
    assert miss == [{"symbol": "MID", "label": "Orta", "reason": "veri yok"}]


def test_tarama_kilidi_doluysa_kosmaz_ve_gunu_yakmaz():
    md = _MD(_market())
    s = _sched(md)
    s._prep_date = TODAY
    s._scan_gate.acquire()
    s._maybe_theme_radar(datetime(2026, 10, 26, 8, 46, tzinfo=ET),
                         TODAY, OPEN, CLOSE)
    assert md.calls == [] and s._radar_date is None   # sonraki tick dener
    s._scan_gate.release()
    s._maybe_theme_radar(datetime(2026, 10, 26, 8, 47, tzinfo=ET),
                         TODAY, OPEN, CLOSE)
    assert len(md.calls) == 1


# ----------------------------------------------------------------- uclar
def test_uclar_pending_rapor_ve_yonetim_korumasi():
    from app.config.settings import Settings
    from app.server import create_app
    from app.services.market_calendar import MarketCalendar
    from app.services.state_store import InMemoryStateStore

    settings = Settings(_env_file=None, TELEGRAM_ENABLED=False,
                        STATE_BACKEND="memory")
    store = InMemoryStateStore()
    sched = Scheduler(settings, None, None, None, MarketCalendar(), store,
                      _Notifier(), None, None)
    c = create_app(store, sched, universe=None).test_client()
    body = c.get("/theme-radar").get_json()
    assert body["pending"] is True and len(body["universe"]) == 18
    assert c.get("/theme-radar/run").status_code == 503   # token tanimsiz

    sched._theme_radar = ThemeRadar(SPEC)
    sched._theme_radar.run(_market(), TODAY)
    body = c.get("/theme-radar").get_json()
    assert body["report"]["asof"] == D_END.isoformat()
    assert body["hot"] == {"HOT": TODAY.isoformat()}
    assert [r["symbol"] for r in body["report"]["rows"]][:2] == ["SUPER", "HOT"]


def test_salt_okur_kopru_radari_kosturamaz():
    """vm-read.sh 'tema' komutu yalniz okur; radari kosturan yonetim
    ucu kopruye girmez (anayasa 4.5: yazan her sey onaya tabi)."""
    src = (ROOT / "ops" / "local" / "vm-read.sh").read_text(encoding="utf-8")
    code = "\n".join(ln for ln in src.splitlines()
                     if not ln.lstrip().startswith("#"))   # yorumlar haric
    assert "/theme-radar\"" in code
    assert "/theme-radar/run" not in code
