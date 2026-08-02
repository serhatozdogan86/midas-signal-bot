"""
yfinance <-> Alpaca veri karsilastirmasi (Asama 0 - salt gozlem).

AMAC: Ana veri kaynagini DEGISTIRMEDEN once "Alpaca gercekten daha mi
guvenilir/eksiksiz?" sorusunu veriyle cevaplamak. Motor kararlarina
HICBIR ETKISI YOKTUR - yalnizca olcum yapar ve rapor uretir.

Olculenler (ornek sembol kumesi uzerinde, gunde bir kez):
  - KAPSAM: iki kaynagin kac sembol dondurdugu (biri digerinde yok mu?)
  - KAPANIS SAPMASI: ortak son kapanis barlarinda yuzde fark
  - BAR SAYISI: ayni donemde kac bar dondugu (eksik veri gostergesi)

Karsilastirma OLUSMAKTA OLAN son bari disarida birakir: Alpaca ucretsiz
planda son 15 dakikayi vermez, yfinance verir - bu yapisal farki hata
gibi raporlamak yaniltici olurdu.
"""
from __future__ import annotations

import logging

from app.logging_setup import kv

log = logging.getLogger("datacmp")

_CLOSE_TOLERANCE_PCT = 0.5      # bu esigin ustundeki sapma "uyusmazlik"


class DataComparisonService:
    """Iki veri kaynagini ayni istekle sorgulayip farklari raporlar."""

    def __init__(self, yf_client, alpaca_client, sample_size: int = 25) -> None:
        self._yf = yf_client
        self._alpaca = alpaca_client
        self._sample = max(1, sample_size)
        self.last_report: dict | None = None

    @property
    def enabled(self) -> bool:
        return self._alpaca is not None and self._alpaca.enabled

    def compare(self, symbols: list[str], interval: str = "1d") -> dict | None:
        """Ornek sembol kumesinde iki kaynagi karsilastirir ve rapor dondurur."""
        if not self.enabled or not symbols:
            return None
        sample = sorted(dict.fromkeys(s.upper() for s in symbols))[:self._sample]
        try:
            yf_frames = self._yf.download_bulk(sample, interval, "3mo")
        except Exception:
            log.exception(kv(event="datacmp_yf_error"))
            yf_frames = {}
        try:
            al_frames = self._alpaca.download_bulk(sample, interval, lookback_days=90)
        except Exception:
            log.exception(kv(event="datacmp_alpaca_error"))
            al_frames = {}

        yf_syms, al_syms = set(yf_frames), set(al_frames)
        both = sorted(yf_syms & al_syms)

        deviations, mismatches, bar_gaps = [], [], []
        for sym in both:
            y, a = yf_frames[sym], al_frames[sym]
            # olusmakta olan son bar disarida (ucretsiz plan 15 dk kisiti)
            if len(y) < 2 or len(a) < 2:
                continue
            y_close = float(y["Close"].iloc[-2])
            a_close = float(a["Close"].iloc[-2])
            if y_close <= 0:
                continue
            pct = abs(a_close - y_close) / y_close * 100
            deviations.append(pct)
            if pct > _CLOSE_TOLERANCE_PCT:
                mismatches.append({"symbol": sym, "yf": round(y_close, 2),
                                   "alpaca": round(a_close, 2),
                                   "pct": round(pct, 2)})
            gap = len(a) - len(y)
            if abs(gap) > 2:
                bar_gaps.append({"symbol": sym, "yf_bars": len(y),
                                 "alpaca_bars": len(a)})

        deviations.sort()
        n = len(deviations)
        report = {
            "interval": interval,
            "sampled": len(sample),
            "yf_only": sorted(yf_syms - al_syms)[:10],
            "alpaca_only": sorted(al_syms - yf_syms)[:10],
            "yf_count": len(yf_syms),
            "alpaca_count": len(al_syms),
            "compared": n,
            "median_dev_pct": round(deviations[n // 2], 3) if n else None,
            "max_dev_pct": round(deviations[-1], 3) if n else None,
            "mismatches": sorted(mismatches, key=lambda m: -m["pct"])[:5],
            "mismatch_count": len(mismatches),
            "bar_gaps": bar_gaps[:5],
        }
        self.last_report = report
        log.info(kv(event="datacmp_done", sampled=len(sample),
                    yf=len(yf_syms), alpaca=len(al_syms),
                    median_dev=report["median_dev_pct"],
                    mismatches=len(mismatches)))
        return report

    def summary_line(self) -> str:
        """Gun sonu raporu icin tek satirlik ozet."""
        r = self.last_report
        if not r:
            return ""
        parts = [f"Veri kiyasi ({r['interval']}, {r['sampled']} sembol): "
                 f"yfinance {r['yf_count']} / Alpaca {r['alpaca_count']} sembol"]
        if r["median_dev_pct"] is not None:
            parts.append(f"kapanis sapmasi medyan %{r['median_dev_pct']}"
                         f" (maks %{r['max_dev_pct']})")
        if r["mismatch_count"]:
            top = r["mismatches"][0]
            parts.append(f"{r['mismatch_count']} uyusmazlik "
                         f"(en buyuk {top['symbol']} %{top['pct']})")
        if r["yf_only"]:
            parts.append(f"yalniz yfinance'te: {', '.join(r['yf_only'][:3])}")
        if r["alpaca_only"]:
            parts.append(f"yalniz Alpaca'da: {', '.join(r['alpaca_only'][:3])}")
        return " | ".join(parts)
