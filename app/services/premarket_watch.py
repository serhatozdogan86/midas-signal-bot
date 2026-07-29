"""
Premarket gap nobeti - acilis oncesi (acilis-30dk .. acilis) TEK SEFERLIK kontrol.
Onaylanmis plan eki (2026-07-29): seans disinda SINYAL URETILMEZ; yalnizca
gap riski eyleme donusturulebilir istihbarata cevrilir. Midas uzatilmis islem
saatlerini (11:00-16:30 / 23:00-03:00 TR, limit emir) desteklediginden kullanici
gerekirse pre-market'te pozisyon kapatabilir.

Kontrol edilen iki dar liste (Finnhub 60 cagri/dk limitine saygili, <=20 sembol):
1. ACIK POZISYONLAR (golge takipteki FILLED/PENDING sinyaller):
   - FILLED + pre-market fiyat stop'un otesinde -> "gap-through-stop" uyarisi
     (pre-market limit emirle cikis secenegi hatirlatilir)
   - FILLED + fiyat TP1'in otesinde -> lehte gap bilgisi (kar realizasyonu)
   - PENDING + buyuk gap -> giris bolgesi gecersizlesebilir notu
2. IZLEME LISTESI ADAYLARI: onceki kapanisa gore >= esik gap -> setup suphesi.

Saf fonksiyonlar: quote/kapanis sozlukleri disaridan verilir; ag I/O scheduler'da.
"""
from __future__ import annotations


def build_gap_report(open_signals: list[dict], candidates: list[str],
                     quotes: dict[str, float], prev_closes: dict[str, float],
                     alert_pct: float = 3.0) -> dict:
    position_alerts: list[str] = []
    candidate_alerts: list[str] = []
    checked = 0

    for sig in open_signals:
        symbol = sig.get("symbol")
        quote = quotes.get(symbol)
        if quote is None:
            continue
        checked += 1
        is_long = sig.get("direction") == "LONG"
        status = sig.get("status")
        prev = prev_closes.get(symbol)
        gap_pct = (round((quote / prev - 1) * 100, 1)
                   if prev else None)
        gap_txt = f" (gap {gap_pct:+.1f}%)" if gap_pct is not None else ""

        if status == "FILLED":
            stop, tp1 = sig.get("stop_loss"), sig.get("tp1")
            stop_breached = (stop is not None
                             and (quote <= stop if is_long else quote >= stop))
            tp_breached = (tp1 is not None
                           and (quote >= tp1 if is_long else quote <= tp1))
            if stop_breached:
                position_alerts.append(
                    f"{symbol} {sig.get('direction')}: pre-market {quote:g}, "
                    f"STOP'un ({stop:g}) OTESINDE{gap_txt}. Acilis daha kotu "
                    "olabilir; Midas'ta pre-market LIMIT emirle cikisi "
                    "degerlendir.")
            elif tp_breached:
                position_alerts.append(
                    f"{symbol} {sig.get('direction')}: pre-market {quote:g}, "
                    f"TP1'in ({tp1:g}) OTESINDE{gap_txt}. Lehte gap - "
                    "pre-market kar realizasyonu bir secenek.")
            elif gap_pct is not None and abs(gap_pct) >= alert_pct:
                position_alerts.append(
                    f"{symbol} {sig.get('direction')}: belirgin gap "
                    f"{gap_pct:+.1f}% (pre-market {quote:g}). Acilista "
                    "oynaklik bekle; stop disiplinini hatirla.")
        elif status == "PENDING" and gap_pct is not None \
                and abs(gap_pct) >= alert_pct:
            position_alerts.append(
                f"{symbol} {sig.get('direction')} (henuz dolmadi): gap "
                f"{gap_pct:+.1f}%. Giris bolgesi gecersizlesmis olabilir; "
                "kovalamak yok.")

    for symbol in candidates:
        quote, prev = quotes.get(symbol), prev_closes.get(symbol)
        if quote is None or not prev:
            continue
        checked += 1
        gap_pct = round((quote / prev - 1) * 100, 1)
        if abs(gap_pct) >= alert_pct:
            candidate_alerts.append(
                f"{symbol}: {gap_pct:+.1f}% gap - dunku setup yapisi "
                "suphali, acilis sonrasi yeniden degerlendirilecek.")

    return {"position_alerts": position_alerts,
            "candidate_alerts": candidate_alerts,
            "checked": checked}


def render_gap_report(report: dict) -> str | None:
    """Bildirilecek bir sey yoksa None (mesaj spam'i yapilmaz)."""
    pos, cand = report["position_alerts"], report["candidate_alerts"]
    if not pos and not cand:
        return None
    lines = ["Acilis oncesi gap nobeti"]
    if pos:
        lines.append("Pozisyonlar:")
        lines += [f"  ! {a}" for a in pos]
    if cand:
        lines.append("Adaylar:")
        lines += [f"  - {a}" for a in cand]
    lines.append("Not: pre-market likiditesi incedir; islem yalniz LIMIT "
                 "emirle, fiyat teyidiyle. Yatirim tavsiyesi degildir.")
    return "\n".join(lines)
