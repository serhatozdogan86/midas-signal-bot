"""HIPOTEZ LABORATUVARI (v3.21): hacim filtresine takilan PULLBACK'lerin
varsayimsal takibi. YALNIZCA GOZLEM - karara, portfoy tavanlarina, karneye
ve Telegram'a KARISMAZ (blocked=5 kohortu; tum skor sorgulari blocked=0).

Hipotez (6 Agu decision-arsiv bulgusu): tetik mumunda >=1.3x hacim sarti
breakout icin dogal (kirilim hacimle gelir) ama pullback icin yapisal
olarak celiskili - geri cekilme tanim geregi dusuk hacimli bir evredir.
Son 2000 kararda pullback 8 kez bulundu ve 8'inde de VOLUME kesti; defter
fiilen tek-setup (breakout_retest) kaldi. Bu modul "hacim sarti pullback'e
uygulanmasaydi ne olurdu" sorusunu gercek ileri-veriyle olcer (hypo_r).

KILIT NOTU (docs/config-lock.md): strategies/ DEGISMEDI, engine_sha ayni.
Bu modul motorun SAF fonksiyonlarini yalnizca CAGIRIR. Hacim disindaki
tum kapilar (RR bandi 2.0-6.0, maliyet filtresi TP1>=%2) AYNEN uygulanir;
boylece kohort canli defterden YALNIZ hacim kosuluyla ayrisir ve fark
dogrudan hipoteze atfedilebilir. Gercek hacim orani block_reason'a
yazilir - analiz asamasinda "esik 1.0x olsaydi" gibi alt kumeler kesilebilir.
"""
from __future__ import annotations

import logging

from app.logging_setup import kv
from app.models.candle import KlineSeries
from app.models.decision import (
    Bias, Confidence, Decision, DecisionType, Direction, EntryZone,
    MarketRegime, SetupType, Targets,
)
from app.strategies import relative_strength, structure_analyzer
from app.strategies.risk_manager import build_trade_plan
from app.strategies.volume_analyzer import validate_event_volume

log = logging.getLogger("hypo_lab")

# blocked sinif haritasi: 2=portfoy tavani, 3=kill-switch, 4=acilis
# penceresi (session_guard). 5 = hacim/pullback hipotezi (bu modul).
BLOCKED_HYPO_VOLUME = 5


def eligible(d: Decision) -> bool:
    """Kanca on-kosulu: yalniz-hacimde elenen pullback adayi."""
    return (d.decision is DecisionType.NO_TRADE
            and d.failed_filters == ["VOLUME"]
            and d.setup_type is SetupType.TREND_PULLBACK
            and d.trend_bias in (Bias.BULLISH, Bias.BEARISH))


def build_volume_hypo(d: Decision,
                      daily_series: KlineSeries,
                      hourly_series: KlineSeries,
                      regime, params,
                      benchmark_daily=None) -> tuple[Decision, str] | None:
    """VOLUME reddinden varsayimsal sinyal kur. Kurulamazsa None.

    Motorun 7-9. adimlarini (confluence, RR kapilari, plan) saf cagrilarla
    AYNEN tekrarlar; tek fark hacim kosulunun atlanmasidir. RR/maliyet
    kapisini gecemeyen aday hipoteze de GIRMEZ - aksi halde kohort "hacim
    olmasaydi" degil "hicbir filtre olmasaydi" sorusunu olcerdi (yanlilik).
    """
    if not eligible(d):
        return None
    direction = (Direction.LONG if d.trend_bias is Bias.BULLISH
                 else Direction.SHORT)
    hourly = hourly_series.closed_only().to_dataframe()
    daily = daily_series.to_dataframe()

    # Setup'i deterministik yeniden bul (ayni saf fonksiyon, ayni veri).
    setup = structure_analyzer.detect_setup(hourly, direction, params)
    if setup is None or setup.setup_type is not SetupType.TREND_PULLBACK:
        return None

    # Gercek hacim orani - kayit/analiz icin (karar girdisi DEGIL).
    tightened = regime.regime is MarketRegime.NEUTRAL
    vol_mult = params.volume_mult + (params.neutral_volume_bump
                                     if tightened else 0.0)
    _, vol_ratio = validate_event_volume(hourly, setup.event_index, vol_mult)

    # RR + maliyet kapilari: motordakiyle birebir ayni esikler.
    plan = build_trade_plan(hourly, daily, direction, setup, params)
    if plan is None:
        return None
    min_rr = params.min_rr + (params.neutral_rr_bump if tightened else 0.0)
    if plan.rr > params.rr_max or plan.rr < min_rr:
        return None
    if plan.target_pct < params.min_target_pct:
        return None

    conf = relative_strength.collect_confluence(daily, benchmark_daily,
                                                direction, vol_ratio, params)
    h = d.model_copy(deep=True)
    h.decision = DecisionType.SIGNAL      # varsayimsal; blocked=5 damgali
    h.direction = direction
    h.entry_zone = EntryZone(min=plan.entry_min, max=plan.entry_max)
    h.stop_loss = plan.stop_loss
    h.targets = Targets(tp1=plan.tp1, tp2=plan.tp2)
    h.rr = plan.rr
    h.target_pct = plan.target_pct
    h.confluence = conf
    h.confidence = (Confidence.HIGH if len(conf) >= 3
                    else Confidence.MEDIUM if len(conf) == 2
                    else Confidence.LOW)
    h.time_stop_days = params.time_stop_days
    h.failed_filters = []
    h.reject_reason = None

    reason = (f"hipotez/hacim: pullback {vol_ratio:.2f}x < {vol_mult:.2f}x "
              f"esigi (yalniz gozlem)")
    log.info(kv(event="hypo_volume_pullback", symbol=d.symbol,
                direction=direction.value, vol_ratio=vol_ratio, rr=plan.rr))
    return h, reason
