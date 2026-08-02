"""
Seans korumasi (v3.9) - iki SAF kural, I/O yok (engine ilkesi korunur):

1) Endeks kill-switch: gun ici endeks tape'i yeni giris yonune sert
   aleyhteyken YENI sinyal acilmaz. 29 Tem dersi: MARKET_REGIME gunluk
   veriyle sabah bir kez hesaplanir, gun icinde KORDUR - SPY -1.4% /
   QQQ -2.0% duserken bot gun boyu long breakout uretti. Bu kural
   yalnizca YENI girisleri keser; acik sinyal yonetimi, gap nobeti ve
   cikislar ETKILENMEZ.

2) Acilis penceresi: acilistan sonraki ilk N dakika breakout tetigi
   calismaz (acilis fake kirilimlari; 29 Tem 13:30 salvosunun panzehiri).
   Pullback/bolge tetikleri etkilenmez; N. dakikadan sonra seviye hala
   gecerliyse normal akis devam eder.

Veri gelmezse FAIL-OPEN (bilincli karar, 2 Agu): koruma katmani veri
hickiriginda botu susturmamali; cagiran taraf WARNING loglar ki eksik
veri nabizda gorunur olsun.

Olcum: bu kurallarin engelledigi adaylar blocked=3 (kill-switch) ve
blocked=4 (acilis penceresi) siniflariyla hypo_r uzerinden izlenir -
korumanin gercekten R kurtarip kurtarmadigi tahmin degil VERI olur
(tavan kohortu blocked=2 ile ayni yanlislanabilirlik ilkesi).
"""
from __future__ import annotations

from dataclasses import dataclass

# blocked sinif sabitleri (signals.blocked kolonu)
BLOCKED_PORTFOLIO = 2     # portfoy tavani (P1 isi motoru)
BLOCKED_KILL_SWITCH = 3   # endeks kill-switch (v3.9)
BLOCKED_OPEN_BLACKOUT = 4  # acilis penceresi (v3.9)

BLOCKED_CLASS_LABELS = {
    BLOCKED_PORTFOLIO: "portfoy tavani",
    BLOCKED_KILL_SWITCH: "endeks kill-switch",
    BLOCKED_OPEN_BLACKOUT: "acilis penceresi",
}


@dataclass(frozen=True)
class GuardVerdict:
    allowed: bool
    reason: str | None = None


def index_kill_switch(direction: str,
                      spy_pct: float | None, qqq_pct: float | None,
                      spy_thresh: float, qqq_thresh: float) -> GuardVerdict:
    """Yeni giris yonu icin endeks tape kontrolu.

    pct degerleri ONCEKI KAPANISA gore % degisimdir (Finnhub quote;
    gap dahil - bilincli tercih: -1.5%'lik tape gap'ten de gelse long
    girisine ayni derecede dusmandir).

    LONG : SPY <= -spy_thresh VEYA QQQ <= -qqq_thresh -> engelle
    SHORT: ayna (SPY >= +spy_thresh VEYA QQQ >= +qqq_thresh) -> engelle
    Esikler buyukluk olarak yorumlanir (isaret cagirandan bagimsiz).
    Veri None ise o bacak degerlendirilmez (fail-open).
    """
    spy_t, qqq_t = abs(spy_thresh), abs(qqq_thresh)
    if direction == "LONG":
        if spy_pct is not None and spy_pct <= -spy_t:
            return GuardVerdict(False, f"endeks kill-switch (SPY {spy_pct:+.2f}%)")
        if qqq_pct is not None and qqq_pct <= -qqq_t:
            return GuardVerdict(False, f"endeks kill-switch (QQQ {qqq_pct:+.2f}%)")
    elif direction == "SHORT":
        if spy_pct is not None and spy_pct >= spy_t:
            return GuardVerdict(False, f"endeks kill-switch (SPY {spy_pct:+.2f}%)")
        if qqq_pct is not None and qqq_pct >= qqq_t:
            return GuardVerdict(False, f"endeks kill-switch (QQQ {qqq_pct:+.2f}%)")
    return GuardVerdict(True)


def in_open_blackout(minutes_since_open: float | None,
                     blackout_min: int) -> bool:
    """Acilistan itibaren ilk `blackout_min` dakika (ve oncesi) -> True.

    minutes_since_open None ise (seans yok / hesaplanamadi) False:
    kaba tarama zaten yalniz seans icinde kosar; manuel /scan cagrilari
    icin de fail-open ilkesi gecerlidir. Negatif dakika (acilis oncesi
    manuel cagri) engellenir - acilis fake'inden once tetik anlamsizdir.
    """
    if blackout_min <= 0 or minutes_since_open is None:
        return False
    return minutes_since_open < blackout_min
