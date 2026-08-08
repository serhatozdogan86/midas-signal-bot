"""v4.23 MOTOR DUZELTME PAKETI - once KIRMIZI yazilan testler (Serhat onayi,
7 Agu; kanitli mekanizma hatalari -> kilit acildi, yeni kohort).

1. RETEST GERCEKTEN ARANIR: eski kod retest/acceptance dilimlerini kirilim
   mumundan baslatiyordu; kirilim mumu seviyeyi asagidan gectigi icin low'u
   neredeyse her zaman tolerans altindaydi -> "breakout+retest" fiilen
   retestsiz kovalama girisiydi (defterin 16/17 islemi bu setap, -12R).
2. ACCEPTANCE = kirilim SONRASI >=2 kapanis (kirilim mumu sayilmaz).
3. REJIM: SMA200 egimi 221 bar ister; 210-220 barlik seride NaN uzerinden
   UNKNOWN yerine NEUTRAL donuyordu (fail-open).
4. HACIM CAPASI: ortalama hacim olay mumundan ONCEKI 20 bardan alinir;
   eski kod hep bugunun ortalamasina bolerdi (tarihi tetik carpitilirdi).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.config.settings import StrategyParams
from app.models.decision import Direction
from app.strategies import structure_analyzer as sa
from app.strategies.regime_detector import classify_index
from app.strategies.volume_analyzer import validate_event_volume
from tests import fixtures as fx

P = StrategyParams()


def _range_then(closes_after: list[float]) -> pd.DataFrame:
    """150 barlik yatay salinim (tepe ~128.6) + verilen devam barlari."""
    base = 128 + 0.6 * np.sin(np.linspace(0, 10 * np.pi, 150))
    return fx.make_series(np.concatenate([base, closes_after])).to_dataframe()


def test_retest_olmadan_breakout_sinyali_yok():
    """Kirilim + guclu devam ama seviyeye GERI DONUS YOK -> aday yok.
    Eski kod kirilim mumunun kendi low'unu retest sayiyordu."""
    # kirilim mumu tolerans bandinin icinde (low'u kacinilmaz olarak
    # bandin altinda - eski kodun 'retest' sandigi sey tam buydu),
    # sonraki barlar seviyeden UZAK (gercek retest yok)
    # seviye pivot HIGH'idir (~129.0); kirilim mumu 129.2 seviyeyi asar
    # ama low'u kacinilmaz olarak tolerans bandinin altindadir - eski
    # kodun 'retest' sandigi tam buydu. Sonraki barlar seviyeden UZAK.
    hourly = _range_then([129.2] + list(np.linspace(131.0, 140.0, 25)))
    assert sa.detect_breakout_retest(hourly, Direction.LONG, P) is None


def test_gercek_retest_aday_uretir():
    """Mevcut fixture gercek retest icerir (kirilim -> acceptance ->
    seviyeye dokunus -> devam): duzeltme sonrasi da aday cikmali."""
    hourly = fx.make_series(fx.hourly_breakout_closes()).to_dataframe()
    cand = sa.detect_breakout_retest(hourly, Direction.LONG, P)
    assert cand is not None
    assert cand.setup_type.value == "breakout_retest"


def test_acceptance_kirilim_mumunu_saymaz():
    """Kirilim sonrasi yalniz 1 kapanis dogru tarafta -> aday yok.
    Eski kod kirilim kapanisini da sayip 2'ye tamamliyordu."""
    hourly = _range_then([128.7, 128.3, 128.5, 128.9])
    assert sa.detect_breakout_retest(hourly, Direction.LONG, P) is None


def test_rejim_yetersiz_bar_unknown():
    """210-220 bar: SMA200 var ama 21-bar-onceki degeri NaN. Eski kod
    NEUTRAL (sikilasmis esikle SINYAL VAR) donuyordu; dogrusu UNKNOWN
    (sinyal yok - fail-closed)."""
    df = pd.DataFrame({"close": np.linspace(50, 150, 215)})
    assert classify_index(df) == "unknown"


def test_rejim_yeterli_barla_calisir():
    df = pd.DataFrame({"close": np.linspace(50, 150, 240)})
    assert classify_index(df) == "bull"


def test_hacim_ortalamasi_olay_mumundan_onceki_pencere():
    """Tarihi tetik mumu, olay SONRASI hacme bolunmemeli. Kurgu: olay
    oncesi ort=100, olay=200 (2.0x); olay sonrasi hacim 1000'e patlar.
    Eski kod bugunun ortalamasina bolup 0.2x der ve teyidi keserdi
    (tersi kurguda hak edilmemis teyit gecerdi)."""
    n = 60
    vols = np.concatenate([np.full(40, 100.0), [200.0], np.full(19, 1000.0)])
    df = pd.DataFrame({"close": np.full(n, 50.0), "volume": vols})
    ok, ratio = validate_event_volume(df, event_index=40, volume_mult=1.3)
    assert ok is True
    assert abs(ratio - 2.0) < 0.05


def test_hacim_son_bar_olayi_ayni_davranis():
    """Olay son bardaysa (pullback yolu) davranis degismemeli."""
    vols = fx.spike_volumes(60, mult=2.0)
    df = pd.DataFrame({"close": np.full(60, 50.0), "volume": vols})
    ok, ratio = validate_event_volume(df, event_index=59, volume_mult=1.3)
    assert ok is True and ratio > 1.8


def test_gunluk_seriler_closed_only_ile_cache_lenir():
    """v4.23: seans ici (re)start'ta bugunun olusmakta olan gunluk bari
    trend/ATR/rejim hesabina girip gun boyu cache'te kaliyordu. Gunluk
    cache artik closed_only ile doldurulur (kaynak tek nokta)."""
    from pathlib import Path
    src = Path("app/scheduler.py").read_text(encoding="utf-8")
    body = src[src.index("def _get_daily_cached"):src.index("def run_coarse_scan")]
    assert "closed_only()" in body


def test_audit_motor_surumu_kilit_oncesi_acik_sinyali_suclamaz(tmp_path):
    """Yeni kilit bilincli baslatildiginda eski kohortun ACIK sinyalleri
    (eski engine_sha) ihlal DEGILDIR; yalniz kilit SONRASI dogan farkli
    sha kohort kirlenmesidir."""
    from app.config.settings import Settings
    from app.services.database import Database
    from app.services.self_audit import run_audit
    from app.services.signal_tracker import SignalTracker

    db = Database(str(tmp_path / "a.db"))
    SignalTracker(db, "1h")
    s = Settings(TELEGRAM_ENABLED=False, STATE_BACKEND="memory",
                 CONFIG_LOCK_UTC="2026-08-08T00:00:00Z")
    db.execute(
        "INSERT INTO signals(symbol,direction,created_utc,status,blocked,"
        "engine_sha) VALUES('OLD','LONG','2026-08-05T14:00:00Z','FILLED',0,"
        "'ESKI999')")
    rep = run_audit(db, engine_sha="YENI111", settings=s)
    chk = next(c for c in rep.checks if c.name == "motor surumu")
    assert chk.ok, f"kilit oncesi acik sinyal suclandi: {chk.detail}"
    db.execute(
        "INSERT INTO signals(symbol,direction,created_utc,status,blocked,"
        "engine_sha) VALUES('NEW','LONG','2026-08-08T14:00:00Z','PENDING',0,"
        "'ESKI999')")
    rep2 = run_audit(db, engine_sha="YENI111", settings=s)
    chk2 = next(c for c in rep2.checks if c.name == "motor surumu")
    assert not chk2.ok
