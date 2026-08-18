"""v4.39: AV hakem araci - saf pencere suzgeci testi (704 sorusturmasi)."""
from __future__ import annotations

from datetime import date

from tools.av_earnings_check import parse_calendar


def test_pencere_suzgeci():
    csv_text = (
        "symbol,name,reportDate,fiscalDateEnding,estimate,currency\n"
        "AAPL,Apple,2026-08-20,2026-06-30,1.5,USD\n"      # pencere ICI
        "MSFT,Microsoft,2026-08-15,2026-06-30,2.0,USD\n"  # pencere ICI (geri 4g)
        "NVDA,Nvidia,2026-09-05,2026-07-31,1.0,USD\n"     # pencere DISI (>14g)
        "BOZUK,X,tarih-degil,,,\n"                        # bozuk satir atlanir
        ",Bos,2026-08-20,,,\n")                           # sembolsuz atlanir
    rep = parse_calendar(csv_text, today=date(2026, 8, 18))
    assert rep["window"] == "2026-08-14..2026-09-01"
    assert rep["window_symbols"] == 2
    assert set(rep["symbols"]) == {"AAPL", "MSFT"}
    assert rep["total_rows"] == 4                          # sembollu satirlar
