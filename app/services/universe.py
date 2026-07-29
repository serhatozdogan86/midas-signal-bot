"""
UniverseProvider - Midas'ta listelenen ABD hisse evreni (plan bolum 2/6).

Kaynak zinciri (dayaniklilik - plan bolum 9 soru 4'e varsayilan cevap):
  1) UNIVERSE_SOURCE=midas -> getmidas.com/amerikan-borsasi scrape
  2) scrape basarisizsa    -> gunluk cache (data/universe_cache.json)
  3) o da yoksa            -> repo icindeki statik yedek liste (haftalik bakim)
UNIVERSE_SOURCE=static ile dogrudan statik liste kullanilir.

Likidite filtresi: son kapanis >= UNIVERSE_MIN_PRICE ve
20 gunluk ortalama dolar hacmi >= UNIVERSE_MIN_DOLLAR_VOL.
Filtrelenmis liste gunde bir kez (hazirlik taramasinda) hesaplanir.
Evren secimi hicbir zaman taramayi durdurmaz.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import date

import requests

from app.config.settings import Settings
from app.logging_setup import kv
from app.models.candle import KlineSeries

log = logging.getLogger("universe")

_TICKER_RE = re.compile(r"^[A-Z]{1,5}(\.[A-Z])?$")
_HREF_RE = re.compile(r"/([A-Za-z][A-Za-z0-9\.\-]{0,5})-hisse", re.IGNORECASE)
_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
# Scrape ciktisindan elenecek genel (hisse olmayan) tokenlar
_BLOCKLIST = {"ABD", "USD", "ETF", "NYSE", "IPO", "CEO", "AI"}


def parse_midas_html(html: str) -> list[str]:
    """Saf parser - testlerde offline HTML fixture ile dogrulanir.

    Iki desen taranir:
      1) '<ticker>-hisse' iceren href slug'lari
      2) tablo hucrelerindeki buyuk harfli kisa kodlar (yedek desen)
    """
    found: set[str] = set()
    for m in _HREF_RE.finditer(html):
        t = m.group(1).upper().replace("-", ".")
        if _TICKER_RE.match(t) and t not in _BLOCKLIST:
            found.add(t)
    if not found:
        for m in re.finditer(r">\s*([A-Z]{1,5}(?:\.[A-Z])?)\s*<", html):
            t = m.group(1)
            if _TICKER_RE.match(t) and t not in _BLOCKLIST:
                found.add(t)
    return sorted(found)


class UniverseProvider:
    def __init__(self, settings: Settings, market_data) -> None:
        self._s = settings
        self._md = market_data  # MarketDataService (likidite filtresi icin)
        self._lock = threading.Lock()
        self._filtered: list[str] = []
        self._filtered_date: date | None = None
        self._raw_count = 0

    # ------------------------------------------------------------ disari API
    def get_symbols(self) -> list[str]:
        """Gunun filtrelenmis listesi; yoksa refresh tetiklenir."""
        with self._lock:
            if self._filtered and self._filtered_date == date.today():
                return list(self._filtered)
        return self.refresh()

    def refresh(self, force: bool = False) -> list[str]:
        """Hazirlik taramasinda cagrilir: kaynak + likidite filtresi + cache."""
        raw = self._load_raw()
        self._raw_count = len(raw)
        filtered = self._liquidity_filter(raw)
        with self._lock:
            if filtered:
                self._filtered = filtered
                self._filtered_date = date.today()
        log.info(kv(event="universe_refresh", raw=len(raw), filtered=len(filtered)))
        return list(filtered)

    def restore(self, symbols: list[str], filtered_date: str | None) -> bool:
        """Deploy sonrasi gist yedeginden evreni tohumla (BUGUNSE gecerli).
        Amac: her yeniden baslatmada 15-20 dk'lik scrape+likidite elemesini
        tekrarlamamak. Eski tarihli yedek kabul edilmez - ertesi gun evren
        yine 15:45 hazirliginda taze kurulur."""
        if not symbols or not filtered_date:
            return False
        try:
            d = date.fromisoformat(filtered_date)
        except ValueError:
            return False
        if d != date.today():
            return False
        with self._lock:
            self._filtered = list(symbols)
            self._filtered_date = d
            self._raw_count = self._raw_count or len(symbols)
        return True

    def describe(self) -> dict:
        with self._lock:
            return {"source": self._s.UNIVERSE_SOURCE, "raw_count": self._raw_count,
                    "filtered_count": len(self._filtered),
                    "filtered_date": (self._filtered_date.isoformat()
                                      if self._filtered_date else None),
                    "min_price": self._s.UNIVERSE_MIN_PRICE,
                    "min_dollar_vol": self._s.UNIVERSE_MIN_DOLLAR_VOL,
                    "symbols": list(self._filtered)}

    # -------------------------------------------------------------- kaynaklar
    def _load_raw(self) -> list[str]:
        if self._s.UNIVERSE_SOURCE.lower() == "midas":
            scraped = self._scrape_midas()
            if len(scraped) >= self._s.UNIVERSE_MIN_EXPECTED:
                self._write_cache(scraped)
                return scraped
            log.warning(kv(event="universe_scrape_insufficient", count=len(scraped)))
            cached = self._read_cache()
            if cached:
                log.info(kv(event="universe_cache_fallback", count=len(cached)))
                return cached
        static = self._static_list()
        log.info(kv(event="universe_static", count=len(static)))
        return static

    def _scrape_midas(self) -> list[str]:
        try:
            resp = requests.get(self._s.MIDAS_UNIVERSE_URL,
                                headers={"User-Agent": _UA}, timeout=(10, 30))
            if resp.status_code != 200:
                log.warning(kv(event="universe_scrape_http", status=resp.status_code))
                return []
            return parse_midas_html(resp.text)
        except requests.RequestException as exc:
            log.warning(kv(event="universe_scrape_error", error=str(exc)[:200]))
            return []

    def _static_list(self) -> list[str]:
        try:
            with open(self._s.STATIC_UNIVERSE_PATH, encoding="utf-8") as f:
                return sorted({line.strip().upper() for line in f
                               if line.strip() and not line.startswith("#")})
        except OSError:
            log.error(kv(event="universe_static_missing",
                         path=self._s.STATIC_UNIVERSE_PATH))
            return []

    def _read_cache(self) -> list[str]:
        try:
            with open(self._s.UNIVERSE_CACHE_PATH, encoding="utf-8") as f:
                return list(json.load(f).get("symbols", []))
        except (OSError, ValueError):
            return []

    def _write_cache(self, symbols: list[str]) -> None:
        try:
            os.makedirs(os.path.dirname(self._s.UNIVERSE_CACHE_PATH) or ".",
                        exist_ok=True)
            with open(self._s.UNIVERSE_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump({"date": date.today().isoformat(), "symbols": symbols}, f)
        except OSError:
            log.warning(kv(event="universe_cache_write_error"))

    # -------------------------------------------------------- likidite filtresi
    def _liquidity_filter(self, symbols: list[str]) -> list[str]:
        """Toplu gunluk veriyle fiyat + dolar hacmi filtresi (plan bolum 5)."""
        if not symbols:
            return []
        daily = self._md.get_daily_bulk(symbols, period="1mo")
        passed: list[tuple[str, float]] = []
        for sym in symbols:
            series: KlineSeries | None = daily.get(sym)
            if series is None or len(series) < 20:
                continue
            df = series.to_dataframe()
            last_close = float(df["close"].iloc[-1])
            dollar_vol = float((df["close"] * df["volume"]).tail(20).mean())
            if last_close >= self._s.UNIVERSE_MIN_PRICE and \
                    dollar_vol >= self._s.UNIVERSE_MIN_DOLLAR_VOL:
                passed.append((sym, dollar_vol))
        passed.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in passed[: self._s.UNIVERSE_MAX_SYMBOLS]]
