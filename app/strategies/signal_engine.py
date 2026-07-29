"""
Signal engine - pipeline orkestrasyonu. SAF FONKSIYON:
I/O yok, global state yok, zaman disaridan enjekte edilebilir (now parametresi).
Girdi: KlineSeries'ler + rejim + earnings bilgisi + StrategyParams -> Cikti: Decision.

Sira sabittir; ilk fail'de kisa devre yapilir (plan bolum 4 - hard filters):
1. DATA           1D/1h mumlar yetersiz              -> DATA_MISSING
2. MARKET_REGIME  endeks verisi yok / yon engelli    -> NO_TRADE
3. TREND          MA hiyerarsisi + HH/HL yok         -> NO_TRADE
                  (short: + zayif RS sarti)
4. EARNINGS       bilancoya +-N islem gunu           -> NO_TRADE
5. SETUP          1h pullback / breakout+retest yok  -> NO_TRADE
6. VOLUME         tetik mumu rel. hacim < esik       -> NO_TRADE
7. (CONFLUENCE    filtre degil, confidence girdisi)
8. RISK_REWARD    RR < esik veya hedef < maliyet     -> NO_TRADE
9. SIGNAL

Short asimetrisi (plan bolum 4): short yalnizca rejim BEAR iken ya da rejim
NEUTRAL + hisse net dusus yapisinda + zayif RS iken uretilir. BULL'da short,
BEAR'da long uretilmez. NEUTRAL'da RR ve hacim esikleri sikilasir.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from app.config.settings import StrategyParams
from app.models.candle import KlineSeries
from app.models.decision import (
    GAP_WARNING_TEXT, Bias, Confidence, Decision, DecisionType, Direction,
    EarningsInfo, EntryZone, MarketRegime, Targets,
)
from app.strategies import relative_strength, structure_analyzer
from app.strategies.regime_detector import RegimeResult
from app.strategies.risk_manager import build_trade_plan
from app.strategies.volume_analyzer import validate_event_volume


def _fmt(v: float) -> str:
    return f"{v:.6g}"


def _allowed_directions(regime: MarketRegime, params: StrategyParams) -> set[Direction]:
    if regime is MarketRegime.BULL:
        allowed = {Direction.LONG}
    elif regime is MarketRegime.BEAR:
        allowed = {Direction.SHORT}
    else:  # NEUTRAL
        allowed = {Direction.LONG, Direction.SHORT}
    if not params.short_enabled:
        allowed.discard(Direction.SHORT)
    return allowed


def evaluate(symbol: str,
             daily_series: KlineSeries | None,
             hourly_series: KlineSeries | None,
             regime: RegimeResult,
             params: StrategyParams,
             benchmark_daily: pd.DataFrame | None = None,
             earnings: EarningsInfo | None = None,
             now: datetime | None = None) -> Decision:
    d = Decision.base(symbol, params.htf, params.mtf, now)
    d.market_regime = regime.regime

    # 1. DATA (gunluk ayak) - 1h kontrolu SETUP oncesine ertelenir.
    # Boylece iki gecisli tarama mumkun olur: 1. gecis yalniz gunluk veriyle
    # rejim/trend/bilanco filtrelerini kosar; 1h verisi SADECE hayatta kalan
    # adaylar icin indirilir (Yahoo rate limitine karsi kritik tasarruf).
    if daily_series is None or len(daily_series) < params.min_bars_daily:
        d.decision = DecisionType.DATA_MISSING
        d.data_missing = ["daily_klines"]
        d.failed_filters = ["DATA"]
        d.reject_reason = "insufficient data"
        return d

    daily = daily_series.to_dataframe()

    # 2. MARKET_REGIME (endeks) - UNKNOWN ise sinyal uretilmez
    if regime.regime is MarketRegime.UNKNOWN:
        d.failed_filters = ["MARKET_REGIME"]
        d.reject_reason = f"endeks rejimi belirsiz ({regime.detail})"
        return d
    allowed = _allowed_directions(regime.regime, params)
    if not allowed:
        d.failed_filters = ["MARKET_REGIME"]
        d.reject_reason = f"rejim {regime.regime.value} + short kapali -> yon yok"
        return d
    tightened = regime.regime is MarketRegime.NEUTRAL

    # 3. TREND (hisse gunluk yapi)
    trend = structure_analyzer.classify_trend(daily, params)
    d.trend_bias = trend.bias
    if trend.bias is Bias.NEUTRAL:
        d.failed_filters = ["TREND"]
        d.reject_reason = f"gunluk trend belirsiz ({trend.detail})"
        d.watch_condition = "MA hiyerarsisi + HH/HL (veya LH/LL) dizilimi bekleniyor"
        return d
    direction = Direction.LONG if trend.bias is Bias.BULLISH else Direction.SHORT
    if direction not in allowed:
        d.failed_filters = ["MARKET_REGIME"]
        d.reject_reason = (f"rejim {regime.regime.value} bu yonu engelliyor "
                           f"({direction.value})")
        d.watch_condition = "endeks rejiminin yonle uyumlanmasi bekleniyor"
        return d
    if direction is Direction.SHORT and params.short_requires_weak_rs:
        rs = None
        if benchmark_daily is not None:
            rs = relative_strength.rs_score(daily["close"], benchmark_daily["close"],
                                            params.rs_lookback_days)
        if rs is None or rs >= 0:
            d.failed_filters = ["TREND"]
            d.reject_reason = f"short icin zayif RS sarti saglanmadi (rs={rs})"
            return d

    # 4. EARNINGS blackout
    if earnings is not None:
        d.earnings_date = earnings.next_date
        d.days_to_earnings = earnings.days_to
        if (earnings.days_to is not None
                and abs(earnings.days_to) <= params.earnings_blackout_days):
            d.failed_filters = ["EARNINGS"]
            d.reject_reason = (f"bilanco blackout: {earnings.next_date} "
                               f"({earnings.days_to:+d} islem gunu)")
            d.watch_condition = "bilanco sonrasi yapinin korunmasi"
            return d

    # DATA (1h ayagi) - gunluk filtrelerden sag cikan aday icin
    if hourly_series is None or len(hourly_series) < params.min_bars_hourly:
        d.decision = DecisionType.DATA_MISSING
        d.data_missing = ["hourly_klines"]
        d.failed_filters = ["DATA"]
        d.reject_reason = "insufficient data"
        return d
    hourly = hourly_series.to_dataframe()

    # 5. SETUP (1h)
    setup = structure_analyzer.detect_setup(hourly, direction, params)
    if setup is None:
        d.failed_filters = ["SETUP"]
        d.reject_reason = "1h setup yok (pullback veya breakout+retest bulunamadi)"
        d.watch_condition = (f"{direction.value}: yukselen/dusen 20EMA'ya geri cekilme "
                             f"+ donus mumu veya kirilim+retest")
        return d
    d.setup_type = setup.setup_type

    # 6. VOLUME
    vol_mult = params.volume_mult + (params.neutral_volume_bump if tightened else 0.0)
    vol_ok, vol_ratio = validate_event_volume(hourly, setup.event_index, vol_mult)
    d.volume_confirmation = vol_ok
    d.volume_note = (f"{setup.setup_type.value} @ {_fmt(setup.level)} "
                     f"(hacim {vol_ratio:.2f}x ort)")
    if not vol_ok:
        d.failed_filters = ["VOLUME"]
        d.reject_reason = (f"tetik mumunda hacim teyidi yok "
                           f"({vol_ratio:.2f}x < {vol_mult:.2f}x)")
        d.watch_condition = "ayni setup, katilim artisiyla"
        return d

    # 7. CONFLUENCE (filtre degil)
    conf = relative_strength.collect_confluence(daily, benchmark_daily, direction,
                                                vol_ratio, params)
    d.confluence = conf

    # 8. RISK_REWARD + maliyet filtresi
    min_rr = params.min_rr + (params.neutral_rr_bump if tightened else 0.0)
    plan = build_trade_plan(hourly, daily, direction, setup, params)
    if plan is None:
        d.failed_filters = ["RISK_REWARD"]
        d.reject_reason = "trade plani kurulamadi (risk<=0)"
        return d
    if plan.rr > params.rr_max:
        # v3 portu (bybit golge verisi dersi): asiri dar stop'tan dogan
        # "fantezi RR" planlari gercekte tutmaz; tavani asan plan reddedilir.
        d.failed_filters = ["RISK_REWARD"]
        d.reject_reason = (f"RR {plan.rr:.2f} > tavan {params.rr_max:.1f} "
                           f"(asiri dar stop suphesi)")
        d.watch_condition = "daha genis/yapisal stop ile makul RR"
        return d
    if plan.rr < min_rr:
        d.failed_filters = ["RISK_REWARD"]
        d.reject_reason = f"RR {plan.rr:.2f} < min {min_rr:.1f}"
        d.watch_condition = "daha derin geri cekilmede daha iyi giris"
        return d
    if plan.target_pct < params.min_target_pct:
        d.failed_filters = ["RISK_REWARD"]
        d.reject_reason = (f"maliyet filtresi: TP1 mesafesi %{plan.target_pct:.2f} "
                           f"< %{params.min_target_pct:.1f} (islem ucreti/spread)")
        return d

    # 9. SIGNAL
    d.decision = DecisionType.SIGNAL
    d.direction = direction
    d.entry_zone = EntryZone(min=plan.entry_min, max=plan.entry_max)
    d.stop_loss = plan.stop_loss
    d.targets = Targets(tp1=plan.tp1, tp2=plan.tp2)
    d.rr = plan.rr
    d.target_pct = plan.target_pct
    d.time_stop_days = params.time_stop_days
    d.gap_warning = GAP_WARNING_TEXT
    d.confidence = (Confidence.HIGH if len(conf) >= 3
                    else Confidence.MEDIUM if len(conf) == 2 else Confidence.LOW)
    side = "altinda" if direction is Direction.LONG else "ustunde"
    d.invalidation = (f"1h kapanis {_fmt(plan.stop_loss)} {side} veya "
                      f"{_fmt(setup.level)} seviyesinin {side} kabul")
    return d
