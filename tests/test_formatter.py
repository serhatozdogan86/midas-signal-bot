"""Telegram formatter testleri - ABD hisse sablonu alanlari."""
from __future__ import annotations

from app.formatting import telegram_formatter as tf
from app.models.decision import (
    GAP_WARNING_TEXT, Confidence, Decision, DecisionType, Direction, EntryZone,
    MarketRegime, Targets,
)


def _signal() -> Decision:
    d = Decision.base("AAPL", "1d", "1h")
    d.decision = DecisionType.SIGNAL
    d.direction = Direction.LONG
    d.market_regime = MarketRegime.BULL
    d.entry_zone = EntryZone(min=98.5, max=99.2)
    d.stop_loss = 97.6
    d.targets = Targets(tp1=101.2, tp2=103.9)
    d.rr = 3.8
    d.target_pct = 2.4
    d.confidence = Confidence.HIGH
    d.time_stop_days = 4
    d.time_stop_date = "2026-08-03"
    d.earnings_date = "2026-08-20"
    d.days_to_earnings = 8
    d.gap_warning = GAP_WARNING_TEXT
    d.invalidation = "1h kapanis 97.6 altinda"
    d.volume_note = "trend_pullback @ 98.6 (hacim 2.00x ort)"
    d.confluence = ["RS(63g) SPY ustunde"]
    return d


def test_render_signal_contains_us_fields():
    text = tf.render(_signal())
    assert "SINYAL | AAPL | LONG" in text
    assert "Time-stop: 4 islem gunu (2026-08-03)" in text
    assert "Bilanco: 2026-08-20 (+8 islem gunu)" in text
    assert GAP_WARNING_TEXT in text
    assert "TP1: 101.2" in text and "RR: 3.8" in text
    assert "Midas'tan manuel girilir" in text


def test_render_no_trade():
    d = Decision.base("MSFT", "1d", "1h")
    d.reject_reason = "gunluk trend belirsiz"
    d.failed_filters = ["TREND"]
    text = tf.render(d)
    assert "ISLEM YOK | MSFT" in text and "TREND" in text


def test_render_data_missing():
    d = Decision.base("NVDA", "1d", "1h")
    d.decision = DecisionType.DATA_MISSING
    d.data_missing = ["hourly_klines"]
    text = tf.render(d)
    assert "VERI EKSIK | NVDA" in text and "hourly_klines" in text
