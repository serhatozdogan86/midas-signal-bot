"""Sirket temel verileri (fundamentals) servisi.

Dashboard'daki sinyal kartlarina (Acik Pozisyonlar / Bekleyen Sinyaller /
Cikis Nobeti) kisa bir "sirket kimligi" satiri eklemek icin: sektor, F/K,
piyasa degeri, PD/DD, borc/ozkaynak, FAVOK marji. Sinyal motoruna KARISMAZ -
salt bilgi amacli, salt-okunur bir yan servistir.

KOK NEDEN (2 Agu, kanitlandi): yf.Ticker().info yerel/ev IP'sinden
SORUNSUZ calisiyor ama Render'da 5/5 sembolde basarisiz - Yahoo, veri
merkezi IP'lerinde .info (quoteSummary) ucunu engelliyor. Kod hatasi
DEGILDI. Cozum kaynak degisikligi: BIRINCIL Finnhub (/stock/profile2 +
/stock/metric; zaten yapilandirilmis ve Render'dan calisiyor - quote/haber
akiyor), YEDEK yfinance (yerel calistirmada ve Finnhub anahtari yoksa).

Sembol basina uzun omurlu (24 saat) bellek-ici onbellek kullanilir; toplu
istekler ThreadPoolExecutor ile paralel yapilir. Herhangi bir sembolde hata
olursa o sembol sessizce atlanir (dashboard '-'), toplu istek asla patlamaz.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger("fundamentals")

_TTL_SEC = 24 * 3600
_MAX_WORKERS = 8


class FundamentalsService:
    def __init__(self, ttl_sec: int = _TTL_SEC, finnhub=None) -> None:
        self._ttl = ttl_sec
        self._finnhub = finnhub          # None -> yalniz yfinance yedegi
        self._cache: dict[str, tuple[float, dict | None]] = {}
        self._first_call_logged = False
        self.last_source: dict[str, int] = {}   # teshis: kaynak basina basari

    def get_many(self, symbols: list[str]) -> dict[str, dict]:
        """Verilen sembollerin temel verilerini dondurur (onbellekli+paralel).
        Eksik/basarisiz semboller sonuc sozlugunde YER ALMAZ (dashboard '-')."""
        if not self._first_call_logged:
            self._first_call_logged = True
            # Uzaktan teshis (1 Agu): '/fundamentals hic cagriliyor mu' sorusu
            # gist nabzindan cevaplanabilsin diye ILK cagriyi WARNING'e yaz.
            log.warning("fundamentals_first_call source=%s symbols=%s",
                        "finnhub" if (self._finnhub is not None
                                      and getattr(self._finnhub, "configured", False))
                        else "yfinance", ",".join(symbols[:10]))
        now = time.time()
        need = [s for s in symbols
                if now - self._cache.get(s, (0, None))[0] >= self._ttl]
        if need:
            with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(need))) as ex:
                results = list(ex.map(self._fetch_one, need))
            for sym, data in zip(need, results):
                # v4.22: basarisiz fetch 24 saat negatif-cache'lenmesin -
                # Finnhub 10 dk cokse kartlar tum gun '-' kaliyordu.
                # None sonuc 15 dk sonra yeniden denenecek sekilde yazilir.
                stamp = now if data is not None else (now - self._ttl + 900)
                self._cache[sym] = (stamp, data)
            failed = sum(1 for d in results if d is None)
            if failed:
                # kismi de olsa WARNING - gist nabzinda gorunur olsun.
                # v3.9.1: hangi kaynagin ise yaradigi da loglanir.
                log.warning("fundamentals_fetch_failures failed=%d of %d "
                            "sources=%s symbols=%s", failed, len(need),
                            self.last_source or "-", ",".join(need[:10]))
        out = {}
        for s in symbols:
            _, data = self._cache.get(s, (0, None))
            if data:
                out[s] = data
        return out

    def _fetch_one(self, symbol: str) -> dict | None:
        """Once Finnhub (Render'da calisan kaynak), sonra yfinance yedegi."""
        if self._finnhub is not None and getattr(self._finnhub, "configured", False):
            data = self._from_finnhub(symbol)
            if data:
                self.last_source["finnhub"] = self.last_source.get("finnhub", 0) + 1
                return data
        data = self._from_yfinance(symbol)
        if data:
            self.last_source["yfinance"] = self.last_source.get("yfinance", 0) + 1
        return data

    def _from_finnhub(self, symbol: str) -> dict | None:
        """profile2 (sektor + piyasa degeri) zorunlu; metric (oranlar)
        ucretsiz planda kisitli olabilir -> KISMI veri de kabul edilir,
        eksik alanlar None kalir (dashboard '-' gosterir)."""
        try:
            prof = self._finnhub.get_company_profile(symbol)
        except Exception as e:
            log.info("fundamentals_finnhub_failed symbol=%s err=%s",
                     symbol, type(e).__name__)
            return None
        if not prof or not prof.get("finnhubIndustry"):
            return None
        try:
            m = self._finnhub.get_basic_financials(symbol) or {}
        except Exception:
            m = {}

        def _num(*keys):
            for k in keys:
                v = m.get(k)
                if isinstance(v, (int, float)):
                    return float(v)
            return None

        mc = prof.get("marketCapitalization")   # Finnhub: milyon $
        ebitda_margin = _num("ebitdaMarginTTM", "ebitdaMarginAnnual")
        # BIRIM TUZAGI (2 Agu): dashboard borc/ozkaynagi YUZDE olarak
        # basar ('%'+toFixed(0)) cunku yfinance yuzde donduruyordu (210).
        # Finnhub ORAN dondurur (2.10) -> x100 sart, yoksa GM icin
        # "%2" yazardi (gercek: %206). Sozlesme: YUZDE.
        dte = _num("totalDebt/totalEquityQuarterly",
                   "totalDebt/totalEquityAnnual")
        return {
            "sector": prof.get("finnhubIndustry"),
            "industry": prof.get("finnhubIndustry"),
            "pe": _num("peTTM", "peBasicExclExtraTTM", "peAnnual"),
            "market_cap": float(mc) * 1e6 if isinstance(mc, (int, float)) else None,
            "price_to_book": _num("pbQuarterly", "pbAnnual"),
            "debt_to_equity": round(dte * 100, 1) if dte is not None else None,
            "ebitda_margin": round(ebitda_margin, 1)
            if ebitda_margin is not None else None,   # Finnhub zaten yuzde
        }

    @staticmethod
    def _from_yfinance(symbol: str) -> dict | None:
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
