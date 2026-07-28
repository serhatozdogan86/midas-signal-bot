"""
Telegram plain-text formatter - ABD hisse sablonu (plan bolum 6: metin guncellendi).
Sinyal mesajina eklenenler: time-stop, gap uyarisi, bilanco tarihi, maliyet notu.
parse_mode YOK (escape derdi yok); MarkdownV2 zengin mod Phase 3.
"""
from __future__ import annotations

from app.models.decision import Decision, DecisionType

_SEP = "---------------------------"


def _n(v: float | None) -> str:
    return f"{v:.6g}" if v is not None else "-"


def _earnings_line(d: Decision) -> str:
    if not d.earnings_date:
        return "Bilanco: bilinmiyor"
    days = f" ({d.days_to_earnings:+d} islem gunu)" if d.days_to_earnings is not None else ""
    return f"Bilanco: {d.earnings_date}{days}"


def render_signal(d: Decision) -> str:
    conf = "\n".join(f"  + {c}" for c in d.confluence) or "  -"
    time_stop = (f"{d.time_stop_days} islem gunu"
                 + (f" ({d.time_stop_date})" if d.time_stop_date else ""))
    return (
        f"SINYAL | {d.symbol} | {d.direction.value}\n"
        f"{_SEP}\n"
        f"Rejim: {d.market_regime.value} | Trend: {d.trend_bias.value}\n"
        f"Setup: {d.setup_type.value} | Guven: {d.confidence.value}\n"
        f"Giris: {_n(d.entry_zone.min)} - {_n(d.entry_zone.max)}\n"
        f"Stop: {_n(d.stop_loss)}\n"
        f"TP1: {_n(d.targets.tp1)} | TP2: {_n(d.targets.tp2)} | RR: {_n(d.rr)}\n"
        f"TP1 mesafesi: %{_n(d.target_pct)} (maliyet filtresi gecti)\n"
        f"Time-stop: {time_stop}\n"
        f"{_earnings_line(d)}\n"
        f"Hacim: {d.volume_note}\n"
        f"Confluence:\n{conf}\n"
        f"Gecersizlik: {d.invalidation}\n"
        f"UYARI: {d.gap_warning}\n"
        f"{_SEP}\n"
        f"TF: {d.timeframes.htf}/{d.timeframes.mtf} | {d.timestamp_utc}\n"
        f"Karar destegi - yatirim tavsiyesi degildir. Emir Midas'tan manuel girilir."
    )


def render_no_trade(d: Decision) -> str:
    return (
        f"ISLEM YOK | {d.symbol}\n"
        f"{_SEP}\n"
        f"Rejim: {d.market_regime.value} | Trend: {d.trend_bias.value}\n"
        f"Neden: {d.reject_reason or '-'}\n"
        f"Kalan filtre: {', '.join(d.failed_filters) or '-'}\n"
        f"Izle: {d.watch_condition or '-'}\n"
        f"{_SEP}\n"
        f"TF: {d.timeframes.htf}/{d.timeframes.mtf} | {d.timestamp_utc}"
    )


def render_data_missing(d: Decision) -> str:
    return (
        f"VERI EKSIK | {d.symbol}\n"
        f"{_SEP}\n"
        f"Eksik: {', '.join(d.data_missing) or '-'}\n"
        f"Aksiyon: varsayim yapilmadi, sinyal uretilmedi\n"
        f"{_SEP}\n"
        f"TF: {d.timeframes.htf}/{d.timeframes.mtf} | {d.timestamp_utc}"
    )


def render(d: Decision, parse_mode: str = "") -> str:
    if d.decision is DecisionType.SIGNAL:
        return render_signal(d)
    if d.decision is DecisionType.DATA_MISSING:
        return render_data_missing(d)
    return render_no_trade(d)
