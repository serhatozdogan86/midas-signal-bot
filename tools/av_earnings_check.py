"""Alpha Vantage bilanco takvimi HAKEM kontrolu (v4.39, 18 Agu).

NEDEN: 17 Agu'da Finnhub takvimi 1490 -> 704 sembole dustu. Sezonluk
daralma mi (Q2 sezonu bitiyor), Finnhub'da sessiz kisitlama mi?
yfinance nokta kiyasi sinirli; Alpha Vantage EARNINGS_CALENDAR ucu tek
cagrida 3 aylik TAM listeyi verir - bagimsiz ucuncu gorus (katalog
taramasi: docs/research-log kesisim kaydi, Serhat onayi 18 Agu).

KULLANIM (VM'de, salt-okur; bota dokunmaz, restart gerektirmez):
    set -a; . ops/oracle/midas.env; set +a
    .venv/bin/python tools/av_earnings_check.py

Cikti: bizim pencere (-4..+14 gun) icindeki benzersiz sembol sayisi,
ornekler ve (bot.db varsa) evrenle kesisim. HICBIR SEYE YAZMAZ.
"""
from __future__ import annotations

import csv
import io
import os
import sys
from datetime import date, timedelta

WINDOW_BACK = 4          # earnings_service._WINDOW_BACK_DAYS ile ayni
WINDOW_FWD = 14          # earnings_service._WINDOW_FWD_DAYS ile ayni


def parse_calendar(csv_text: str, today: date,
                   back: int = WINDOW_BACK,
                   fwd: int = WINDOW_FWD) -> dict:
    """Saf: AV CSV'sinden pencere ici benzersiz semboller. Test edilir."""
    d_from = today - timedelta(days=back)
    d_to = today + timedelta(days=fwd)
    in_window: dict[str, list[str]] = {}
    total = 0
    for row in csv.DictReader(io.StringIO(csv_text)):
        sym = (row.get("symbol") or "").strip().upper()
        raw = (row.get("reportDate") or "").strip()
        if not sym or not raw:
            continue
        total += 1
        try:
            d = date.fromisoformat(raw)
        except ValueError:
            continue
        if d_from <= d <= d_to:
            in_window.setdefault(sym, []).append(raw)
    return {"total_rows": total, "window_symbols": len(in_window),
            "window": f"{d_from}..{d_to}", "symbols": in_window}


def main() -> int:
    key = os.environ.get("ALPHA_VANTAGE_API_KEY", "").strip()
    if not key:
        print("HATA: ALPHA_VANTAGE_API_KEY ortam degiskeni bos.")
        return 2
    import requests
    r = requests.get("https://www.alphavantage.co/query",
                     params={"function": "EARNINGS_CALENDAR",
                             "horizon": "3month", "apikey": key},
                     timeout=60)
    if r.status_code != 200 or not r.text or r.text.lstrip().startswith("{"):
        # AV hata/limit mesajlarini JSON dondurur; CSV bekliyoruz
        print(f"HATA: beklenmedik cevap (HTTP {r.status_code}): "
              f"{r.text[:200]}")
        return 1
    rep = parse_calendar(r.text, date.today())
    print(f"AV toplam satir            : {rep['total_rows']}")
    print(f"Bizim pencere {rep['window']}")
    print(f"Penceredeki benzersiz sembol: {rep['window_symbols']}")
    sample = sorted(rep["symbols"])[:20]
    print(f"Ornek: {', '.join(sample)}")
    # evrenle kesisim (varsa) - Finnhub'in 704'uyle elmali kiyas icin
    cache = "data/universe_cache.json"
    if os.path.exists(cache):
        try:
            import json
            with open(cache, encoding="utf-8") as f:
                uni = set(json.load(f).get("symbols") or [])
            if uni:
                hit = uni & set(rep["symbols"])
                print(f"Evren kesisimi              : {len(hit)}/{len(uni)}")
        except Exception as e:                      # salt bilgi; kirmasin
            print(f"(evren kesisimi okunamadi: {e!r})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
