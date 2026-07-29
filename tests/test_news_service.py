"""NewsService testleri - sahte Finnhub ile (dedupe, rotasyon, butce)."""
from __future__ import annotations

from datetime import date

from app.services.news_service import NewsService


class FakeFinnhubNews:
    def __init__(self):
        self.company_calls: list[str] = []

    def get_general_news(self, category="general"):
        return [
            {"id": 1, "datetime": 1700000100, "headline": "Fed karari bekleniyor",
             "source": "Reuters", "url": "https://x/1"},
            {"id": 1, "datetime": 1700000100, "headline": "Fed karari bekleniyor",
             "source": "Reuters", "url": "https://x/1"},          # dup
            {"id": 2, "datetime": 1700000200, "headline": "Endeksler yukseliste",
             "source": "CNBC", "url": "https://x/2"},
        ]

    def get_company_news(self, symbol, date_from, date_to):
        self.company_calls.append(symbol)
        return [{"id": f"{symbol}-n", "datetime": 1700000300,
                 "headline": f"{symbol} yeni urun duyurdu",
                 "source": "PR", "url": f"https://x/{symbol}"}]


def test_refresh_dedupe_and_symbol_tag():
    fh = FakeFinnhubNews()
    svc = NewsService(fh, refresh_sec=0, max_symbols=2)
    added = svc.refresh(["AAPL", "MSFT", "NVDA"], date(2026, 7, 29))
    assert added == 4                       # 2 genel (dup dusme) + 2 sirket
    assert fh.company_calls == ["AAPL", "MSFT"]   # butce = 2
    items = svc.items()
    assert items[0]["datetime"] >= items[-1]["datetime"]   # yeni -> eski
    syms = {i["symbol"] for i in items if i["symbol"]}
    assert "AAPL" in syms and "MSFT" in syms


def test_rotation_covers_all_symbols():
    fh = FakeFinnhubNews()
    svc = NewsService(fh, refresh_sec=0, max_symbols=2)
    svc.refresh(["AAPL", "MSFT", "NVDA"], date(2026, 7, 29))
    svc.refresh(["AAPL", "MSFT", "NVDA"], date(2026, 7, 29))
    assert "NVDA" in fh.company_calls       # ikinci turda sira ona geldi


def test_keep_limit():
    class ManyNews(FakeFinnhubNews):
        def get_general_news(self, category="general"):
            return [{"id": i, "datetime": i, "headline": f"h{i}",
                     "source": "s", "url": f"u{i}"} for i in range(100)]
    svc = NewsService(ManyNews(), refresh_sec=0, keep=10)
    svc.refresh([], date(2026, 7, 29))
    assert len(svc.items(100)) == 10
    assert svc.items(100)[0]["datetime"] == 99   # en yeniler tutuldu
