"""Hipotez laboratuvari (v3.21) - blocked=5 hacim/pullback kohortu.

Uc guvence test edilir:
1. KURULUM: VOLUME'da elenen pullback'ten gecerli varsayimsal plan dogar
   (motorla ayni RR/maliyet kapilarindan gecmis olarak).
2. KARANTINA: blocked=5 satirlari karneye (stats/net/open_count/setup_mix)
   ve tavan sayimlarina SIZMAZ; blocked_summary'de sinif bazinda gorunur.
3. KAPILAR: RR kapisini gecemeyen aday hipoteze de girmez (yanlilik yok).
"""
from __future__ import annotations

import numpy as np

from app.config.settings import StrategyParams
from app.models.decision import (
    DecisionType, Direction, EarningsInfo, MarketRegime, SetupType,
)
from app.services import hypo_lab
from app.services.database import Database
from app.services.signal_tracker import SignalTracker
from app.strategies import signal_engine
from app.strategies.regime_detector import RegimeResult
from tests import fixtures as fx

P = StrategyParams()
BULL = RegimeResult(regime=MarketRegime.BULL)
E_FAR = EarningsInfo(next_date="2026-08-20", days_to=8)


def _daily(closes):
    return fx.make_series(closes, interval="1d", spread=0.02)


def _volume_rejected_pullback():
    """test_volume_fail ile ayni senaryo: pullback var, hacim 1.0x."""
    daily = _daily(fx.daily_uptrend_closes())
    hourly = fx.make_series(fx.hourly_pullback_long_closes(),
                            volumes=fx.spike_volumes(110, mult=1.0))
    bench = _daily(fx.daily_mild_downtrend_closes()).to_dataframe()
    d = signal_engine.evaluate("AAPL", daily, hourly, BULL, P, bench, E_FAR)
    assert d.decision is DecisionType.NO_TRADE
    assert d.failed_filters == ["VOLUME"]
    assert d.setup_type is SetupType.TREND_PULLBACK
    return d, daily, hourly, bench


def test_eligible_yalniz_hacim_pullback():
    d, *_ = _volume_rejected_pullback()
    assert hypo_lab.eligible(d) is True
    # SIGNAL karari uygun degil
    d2 = d.model_copy(deep=True)
    d2.decision = DecisionType.SIGNAL
    assert hypo_lab.eligible(d2) is False
    # breakout uygun degil (hipotez pullback'e ozgu)
    d3 = d.model_copy(deep=True)
    d3.setup_type = SetupType.BREAKOUT_RETEST
    assert hypo_lab.eligible(d3) is False
    # baska filtrede elenen uygun degil
    d4 = d.model_copy(deep=True)
    d4.failed_filters = ["SETUP"]
    assert hypo_lab.eligible(d4) is False


def test_hypo_kurulur_ve_motor_kapilarindan_gecer():
    d, daily, hourly, bench = _volume_rejected_pullback()
    out = hypo_lab.build_volume_hypo(d, daily, hourly, BULL, P, bench)
    assert out is not None
    h, reason = out
    assert h.direction is Direction.LONG
    assert h.setup_type is SetupType.TREND_PULLBACK
    assert h.entry_zone.min is not None and h.stop_loss is not None
    assert h.stop_loss < h.entry_zone.min          # long plan tutarliligi
    assert P.min_rr <= h.rr <= P.rr_max            # ayni RR bandi
    assert h.target_pct >= P.min_target_pct        # ayni maliyet filtresi
    assert "hipotez/hacim" in reason
    assert "x <" in reason                         # gercek oran kayitli


def test_rr_kapisini_gecemeyen_hipoteze_girmez():
    d, daily, hourly, bench = _volume_rejected_pullback()
    strict = P.model_copy(deep=True)
    strict.min_rr = 50.0                           # kurulamaz esik
    assert hypo_lab.build_volume_hypo(d, daily, hourly, BULL,
                                      strict, bench) is None


def test_karantina_blocked5_karneye_ve_tavana_sizmaz(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    tracker = SignalTracker(db, mtf_interval="1h")
    d, daily, hourly, bench = _volume_rejected_pullback()
    h, why = hypo_lab.build_volume_hypo(d, daily, hourly, BULL, P, bench)
    h.time_stop_date = "2026-08-12"
    assert tracker.track_blocked(h, hourly, why,
                                 hypo_lab.BLOCKED_HYPO_VOLUME) is True
    # karne / defter sorgulari: hicbirinde iz yok
    assert tracker.open_count() == 0
    assert tracker.open_count_by(Direction.LONG.value) == 0
    assert tracker.stats()["open_signals"] == 0
    assert tracker.net_totals()["decided"] == 0
    assert tracker.setup_mix()["setup"] == {}      # v3.21 blocked=0 filtresi
    # hipotez kendi kovasinda okunur
    bs = tracker.blocked_summary()
    assert bs["total"] == 1 and bs["open"] == 1
    assert bs["by_class"][str(hypo_lab.BLOCKED_HYPO_VOLUME)]["n"] == 1
    # ayni sembol+yon tekrar gelirse coift kayit acilmaz (dedup)
    assert tracker.track_blocked(h, hourly, why,
                                 hypo_lab.BLOCKED_HYPO_VOLUME) is False


def test_gercek_acik_sinyal_varken_hipotez_acilmaz(tmp_path):
    """cift sayim korumasi (v3.9.3 kurali sinif 5 icin de gecerli)."""
    db = Database(str(tmp_path / "t.db"))
    tracker = SignalTracker(db, mtf_interval="1h")
    d, daily, hourly, bench = _volume_rejected_pullback()
    h, why = hypo_lab.build_volume_hypo(d, daily, hourly, BULL, P, bench)
    h.time_stop_date = "2026-08-12"
    real = h.model_copy(deep=True)
    mtf = fx.make_series(np.full(70, 102.0), symbol="AAPL")
    assert tracker.maybe_track(real, mtf) is True          # gercek defter
    assert tracker.track_blocked(h, hourly, why,
                                 hypo_lab.BLOCKED_HYPO_VOLUME) is False
