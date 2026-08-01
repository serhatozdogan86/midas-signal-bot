"""
Output contract - schema v2.0-us (Bybit v1.1 sozlesmesinin ABD hisse uyarlamasi).
Alan isimleri SABITTIR; entegrasyonlar bu sozlesmeye gore parse eder.
decision enum: SIGNAL | NO_TRADE | DATA_MISSING
Yeni alanlar (plan bolum 6): earnings_date, days_to_earnings, time_stop_days,
time_stop_date, gap_warning, target_pct, market_regime.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

SCHEMA_VERSION = "2.0-us"
DISCLAIMER = "Decision support only. Not financial advice."
GAP_WARNING_TEXT = "Gece gap riski: stop seviyesi garantili degildir."


class DecisionType(str, Enum):
    SIGNAL = "SIGNAL"
    NO_TRADE = "NO_TRADE"
    DATA_MISSING = "DATA_MISSING"


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NONE = "NONE"


class MarketRegime(str, Enum):
    """Endeks (SPY/QQQ) rejimi - plan bolum 4 filtre 2."""

    BULL = "BULL"
    BEAR = "BEAR"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


class Bias(str, Enum):
    """Hisse gunluk trend durumu - plan bolum 4 filtre 3."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class SetupType(str, Enum):
    TREND_PULLBACK = "trend_pullback"
    BREAKOUT_RETEST = "breakout_retest"
    NONE = "none"


class Confidence(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class TimeFrames(BaseModel):
    htf: str
    mtf: str


class EntryZone(BaseModel):
    min: float | None = None
    max: float | None = None


class Targets(BaseModel):
    tp1: float | None = None
    tp2: float | None = None


class EarningsInfo(BaseModel):
    """EarningsService ciktisi; engine'e saf girdi olarak gecer."""

    next_date: str | None = None      # YYYY-MM-DD
    days_to: int | None = None        # imzali islem gunu mesafesi (gecmis: negatif)


class Decision(BaseModel):
    """SIGNAL / NO_TRADE / DATA_MISSING kararlarinin tamami icin tek model."""

    schema_version: str = SCHEMA_VERSION
    symbol: str
    timestamp_utc: str
    timeframes: TimeFrames
    decision: DecisionType = DecisionType.NO_TRADE
    direction: Direction = Direction.NONE
    market_regime: MarketRegime = MarketRegime.UNKNOWN
    trend_bias: Bias = Bias.NEUTRAL
    setup_type: SetupType = SetupType.NONE
    setup_level: float | None = None           # EMA20 (pullback) veya kirilim seviyesi (breakout)
    confidence: Confidence = Confidence.LOW
    entry_zone: EntryZone = Field(default_factory=EntryZone)
    stop_loss: float | None = None
    targets: Targets = Field(default_factory=Targets)
    rr: float | None = None
    target_pct: float | None = None            # TP1 mesafesi (%) - maliyet filtresi girdisi
    invalidation: str | None = None
    volume_confirmation: bool = False
    volume_note: str = ""
    confluence: list[str] = Field(default_factory=list)
    failed_filters: list[str] = Field(default_factory=list)
    reject_reason: str | None = None
    watch_condition: str | None = None
    data_missing: list[str] = Field(default_factory=list)
    # ABD hisse alanlari (plan bolum 6)
    earnings_date: str | None = None
    days_to_earnings: int | None = None
    time_stop_days: int | None = None
    time_stop_date: str | None = None          # scheduler takvimle zenginlestirir
    gap_warning: str = ""
    disclaimer: str = DISCLAIMER

    def contract_dict(self) -> dict:
        """Makinece parse edilebilir sabit JSON temsili."""
        return self.model_dump(mode="json")

    @classmethod
    def base(cls, symbol: str, htf: str, mtf: str, now: datetime | None = None) -> "Decision":
        now = now or datetime.now(timezone.utc)
        return cls(
            symbol=symbol,
            timestamp_utc=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            timeframes=TimeFrames(htf=htf, mtf=mtf),
        )
