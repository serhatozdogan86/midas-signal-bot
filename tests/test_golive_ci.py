"""v4.30: go-live kapisina istatistik sarti (12 Agu 2026, Bulgu 7).

VAKA: net-R sapmasi ~1.1 iken +0.15R beklenti esigi 60 islemde ~1
standart hataya denk - hic ustunlugu olmayan bir sistem eski besli
kapiyi %15-25 ihtimalle gecebiliyordu. Yeni sart: kume-blok bootstrap
%95 guven araliginin ALT siniri > 0.

Kirilabilirlik: test_sansli_defter_eski_kapiyi_gecerdi_yenisini_gecemez
tam olarak raporun senaryosunu kurar - beklentisi esigi asan ama
istatistiksel olarak ayirt edilemeyen bir defter. v4.30 oncesi kodda
'ci_low_r' anahtari olmadigi icin bu test KeyError ile kirmizi yanar
(kosarak kanitlandi, commit mesajina bkz); yeni kodda kapi kapali kalir.
"""
from __future__ import annotations

from app.config.settings import Settings
from app.scheduler import Scheduler
from app.services.database import Database
from app.services.market_calendar import MarketCalendar
from app.services.signal_tracker import SignalTracker
from app.services.state_store import InMemoryStateStore
from tests.test_scheduler import FakeNotifier


def _tracker(tmp_path):
    return SignalTracker(Database(str(tmp_path / "ci.db")), "1h")


def _closed(db, i, r, cluster):
    """Sonuclanmis islem; giris 100/stop 98 -> maliyet ~0.08R (sabit)."""
    db.execute(
        "INSERT INTO signals(symbol,direction,created_utc,entry_candle_ts,"
        "entry_min,entry_max,stop_loss,tp1,tp2,rr,status,outcome,"
        "r_multiple,closed_utc,fill_price,cluster_id) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (f"T{i}", "LONG", f"2026-08-{8 + i % 20:02d}T14:00:00Z", 1000,
         100.0, 101.0, 98.0, 106.0, 110.0, 2.5, "CLOSED",
         "WIN" if r > 0 else "LOSS", r,
         f"2026-08-{9 + i % 20:02d}T15:00:00Z", 100.0, cluster))


def _sched(tracker, **over):
    settings = Settings(TELEGRAM_ENABLED=False, STATE_BACKEND="memory",
                        CONFIG_LOCK_UTC="2026-08-01T00:00:00Z",
                        GOLIVE_CI_BOOT_N=2000, **over)
    return Scheduler(settings, None, None, None, MarketCalendar(),
                     InMemoryStateStore(), FakeNotifier(), tracker)


def test_ci_deterministik_ve_memolu(tmp_path):
    """Ayni defter ayni araligi verir (sabit tohum); ikinci cagri memo'dan
    doner ('sansli tohum' tartismasi ve tick icinde 10k tur olmasin)."""
    tr = _tracker(tmp_path)
    for i in range(6):
        _closed(tr._db, i, 1.0 if i % 2 else -0.5, f"LONG-2026-08-{10 + i}")
    a = tr.cluster_bootstrap_ci(n_boot=2000)
    b = tr.cluster_bootstrap_ci(n_boot=2000)
    assert a == b
    assert a["clusters"] == 6 and a["trades"] == 6
    assert a["ci_low"] is not None and a["ci_low"] < a["ci_high"]


def test_veri_azken_fail_closed(tmp_path):
    """Kume < 2 -> aralik tanimsiz -> ci_low None ve kapi KAPALI kalir.
    'Veri yok' ile 'engel yok' ayni sey degildir (CLAUDE.md 2.2)."""
    tr = _tracker(tmp_path)
    g = _sched(tr).golive_status()
    assert g["criteria"]["ci_low_r"]["now"] is None
    assert g["criteria"]["ci_low_r"]["ok"] is False
    assert g["met"] is False
    _closed(tr._db, 0, 2.0, "LONG-2026-08-10")     # tek kume de yetmez
    ci = tr.cluster_bootstrap_ci(n_boot=200)
    assert ci["clusters"] == 1 and ci["ci_low"] is None


def test_sansli_defter_eski_kapiyi_gecerdi_yenisini_gecemez(tmp_path):
    """Raporun senaryosu: beklenti esigi ASAN ama sanstan ayirt
    EDILEMEYEN defter. 30 kume: 10 x +2.2R, 20 x -0.62R -> net beklenti
    ~+0.24R (esik 0.15'i gecer, eski BES kriter de yesil) ama sapma
    buyuk; CI alt siniri sifirin altinda -> kapi KAPALI kalir."""
    tr = _tracker(tmp_path)
    vals = []
    for i in range(30):
        vals.append(2.2 if i % 3 == 0 else -0.62)   # 10 kazanc / 20 kayip, serpistirilmis
    for i, r in enumerate(vals):
        _closed(tr._db, i, r, f"LONG-C{i:02d}")
    g = _sched(tr, GOLIVE_MIN_DECIDED=30, GOLIVE_MIN_CLUSTERS=30).golive_status()
    c = g["criteria"]
    # eski besli kapinin tamami yesil...
    assert c["decided"]["ok"] and c["clusters"]["ok"]
    assert c["max_cluster_share"]["ok"] and c["max_dd_r"]["ok"]
    assert c["expectancy_r"]["ok"] and c["expectancy_r"]["now"] >= 0.15
    # ...ama istatistik sarti tesadufu yakalar: v4.30 oncesi met=True idi
    assert c["ci_low_r"]["now"] < 0
    assert c["ci_low_r"]["ok"] is False
    assert g["met"] is False


def test_tutarli_ustunluk_kapiyi_acar(tmp_path):
    """Sart asilamaz bir duvar DEGIL: her kumesi pozitif, tutarli bir
    defter CI alt sinirini sifirin ustune tasir ve kapi acilir.
    (v4.43: KILIT-2 yanlislandigi icin varsayilan ayarlarda kapi kapali;
    bu test kapi MEKANIGINI olctugunden yanlislama notu bosaltilir -
    KILIT-3 dunyasinin provasi.)"""
    tr = _tracker(tmp_path)
    for i in range(30):
        _closed(tr._db, i, 0.9 + (i % 3) * 0.3, f"LONG-P{i:02d}")
    g = _sched(tr, GOLIVE_MIN_DECIDED=30, GOLIVE_MIN_CLUSTERS=30,
               COHORT_FALSIFIED_NOTE="").golive_status()
    assert g["criteria"]["ci_low_r"]["now"] > 0
    assert g["criteria"]["ci_low_r"]["ok"] is True
    assert g["met"] is True


def test_yanlislanan_kohortta_kapi_hicbir_kosulda_acilamaz(tmp_path):
    """v4.43 (20 Agu, Serhat karari B): yanlislama tetiklendikten sonra
    TUM kriterler yesile donse bile kapi ACILMAZ - maksDD tarihsel tepe,
    kohort matematiksel olarak olu; 'met' zorla False, durum raporda.
    Eski kodda bu test kirmizi (state alani yok, met True olurdu)."""
    tr = _tracker(tmp_path)
    for i in range(30):
        _closed(tr._db, i, 0.9 + (i % 3) * 0.3, f"LONG-P{i:02d}")
    g = _sched(tr, GOLIVE_MIN_DECIDED=30,
               GOLIVE_MIN_CLUSTERS=30).golive_status()   # varsayilan: yanlislandi
    assert "YANLISLANDI" in g.get("state", "")
    assert all(v["ok"] for v in g["criteria"].values())  # kriterler yesil...
    assert g["met"] is False                             # ...ama kapi KAPALI
