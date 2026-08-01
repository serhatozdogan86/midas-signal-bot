"""Sirket temel verileri (fundamentals) servisi.

Dashboard'daki sinyal kartlarina (Acik Pozisyonlar / Bekleyen Sinyaller /
Cikis Nobeti) kisa bir "sirket kimligi" satiri eklemek icin: sektor, F/K,
piyasa degeri, PD/DD, borc/ozkaynak, FAVOK marji. Sinyal motoruna KARISMAZ -
salt bilgi amacli, salt-okunur bir yan servistir.

yfinance .info cagrisi agir olabilecegi (ag + coklu istek) icin sembol
basina uzun omurlu (24 saat) bellek-ici onbellek kullanilir; toplu istekler
ThreadPoolExecutor ile paralel yapilir. Herhangi bir sembolde hata olursa
o sembol sessizce atlanir (dashboard '-' gosterir), toplu istek asla patlamaz.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger("fundamentals")

_TTL_SEC = 24 * 3600
_MAX_WORKERS = 8


class FundamentalsService:
    def __init__(self, ttl_sec: int = _TTL_SEC) -> None:
        self._ttl = ttl_sec
        self._cache: dict[str, tuple[float, dict | None]] = {}
        self._first_call_logged = False

    def get_many(self, symbols: list[str]) -> dict[str, dict]:
        """Verilen sembollerin temel verilerini dondurur (onbellekli+paralel).
        Eksik/basarisiz semboller sonuc sozlugunde YER ALMAZ (dashboard '-')."""
        if not self._first_call_logged:
            self._first_call_logged = True
            # Uzaktan teshis (1 Agu): '/fundamentals hic cagriliyor mu' sorusu
            # gist nabzindan cevaplanabilsin diye ILK cagriyi WARNING'e yaz.
            log.warning("fundamentals_first_call symbols=%s", ",".join(symbols[:10]))
        now = time.time()
        need = [s for s in symbols
                if now - self._cache.get(s, (0, None))[0] >= self._ttl]
        if need:
            with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(need))) as ex:
                results = list(ex.map(self._fetch_one, need))
            for sym, data in zip(need, results):
                self._cache[sym] = (now, data)
            failed = sum(1 for d in results if d is None)
            if failed:
                # kismi de olsa artik WARNING - gist nabzinda gorunur olsun
                # (once sessizce yutuluyordu, teshis imkansizdi)
                log.warning("fundamentals_fetch_failures failed=%d of %d symbols=%s",
                           failed, len(need), ",".join(need[:10]))
        out = {}
        for s in symbols:
            _, data = self._cache.get(s, (0, None))
            if data:
                out[s] = data
        return out

    @staticmethod
    def _fetch_one(symbol: str) -> dict | None:
        info = None
        for attempt in range(2):                    # Yahoo bazen ilk denemede
            try:                                     # bos/kesintili donebiliyor
                import yfinance as yf

                # yfinance logger'i gec yapilandiriliyor (bilinen davranis) -
                # import aninda bastir (universe/candle istemcisindeki ayni desen)
                _yl = logging.getLogger("yfinance")
                _yl.setLevel(logging.CRITICAL)
                _yl.propagate = False

                tk = yf.Ticker(symbol)
                info = tk.get_info() if hasattr(tk, "get_info") else tk.info
            except Exception as e:
                if attempt == 0:
                    time.sleep(0.4)
                    continue
                log.info("fundamentals_fetch_failed symbol=%s err=%s",
                         symbol, type(e).__name__)
                return None
            if info and info.get("sector"):
                break
            if attempt == 0:
                time.sleep(0.4)
        if not info or not info.get("sector"):
            return None

        def _num(key):
            v = info.get(key)
            return float(v) if isinstance(v, (int, float)) else None

        return {
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "pe": _num("trailingPE"),
            "market_cap": _num("marketCap"),
            "price_to_book": _num("priceToBook"),
            "debt_to_equity": _num("debtToEquity"),
            "ebitda_margin": (
                round(_num("ebitdaMargins") * 100, 1)
                if _num("ebitdaMargins") is not None else None
            ),
        }
