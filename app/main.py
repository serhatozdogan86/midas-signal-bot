"""
Entrypoint - bagimlilik kablolamasi (composition root).
Calistirma: python -m app.main

Faz 1 kablolamasi:
- STATE_BACKEND=sqlite -> cooldown/sonuclar DB'de (Render free'de disk ephemeral)
- yfinance (tarihsel) + Finnhub (earnings takvimi; quote Phase 2)
- Evren: Midas scrape -> cache -> statik yedek zinciri + likidite filtresi
Phase 3 rezervleri: shadow tracking, gist yedekleme, dashboard.
"""
from __future__ import annotations

import logging
import os

from app.config.settings import get_settings
from app.integrations.finnhub_client import FinnhubClient
from app.integrations.telegram_notifier import TelegramNotifier
from app.integrations.yfinance_client import YFinanceClient
from app.logging_setup import kv, setup_logging
from app.scheduler import Scheduler
from app.server import create_app
from app.services.database import Database
from app.services.earnings_service import EarningsService
from app.services.market_calendar import MarketCalendar
from app.services.market_data_service import MarketDataService
from app.services.sqlite_state_store import SQLiteStateStore
from app.services.state_store import InMemoryStateStore
from app.services.universe import UniverseProvider

log = logging.getLogger("main")


def main() -> None:
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)

    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        log.warning(kv(event="telegram_env_missing",
                       note="bot calisir ama mesaj gonderemez (/scan/dry kullanilabilir)"))
    if not settings.FINNHUB_API_KEY:
        log.warning(kv(event="finnhub_env_missing",
                       note="bilanco takvimi bos kalir; EARNINGS filtresi pasif olur"))

    # --- kalicilik ---
    if settings.STATE_BACKEND.lower() == "sqlite":
        store = SQLiteStateStore(Database(settings.DB_PATH))
    else:
        store = InMemoryStateStore()

    # --- veri katmani (iki kaynakli) ---
    yf_client = YFinanceClient(settings.YF_CHUNK_SIZE, settings.YF_CHUNK_PAUSE_SEC)
    finnhub = FinnhubClient(settings.FINNHUB_API_KEY, settings.FINNHUB_BASE_URL)
    market_data = MarketDataService(yf_client, finnhub,
                                    settings.DAILY_PERIOD, settings.HOURLY_PERIOD)

    # --- servisler ---
    calendar = MarketCalendar()
    universe = UniverseProvider(settings, market_data)
    earnings = EarningsService(finnhub, calendar)
    notifier = TelegramNotifier(settings.TELEGRAM_BOT_TOKEN,
                                settings.TELEGRAM_CHAT_ID,
                                settings.TELEGRAM_PARSE_MODE)

    scheduler = Scheduler(settings, market_data, universe, earnings,
                          calendar, store, notifier)
    app = create_app(store, scheduler, universe)

    scheduler.start_background()
    port = int(os.getenv("PORT", "10000"))
    log.info(kv(event="server_start", port=port,
                state_backend=settings.STATE_BACKEND,
                universe_source=settings.UNIVERSE_SOURCE))
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
