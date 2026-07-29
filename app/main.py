"""
Entrypoint - bagimlilik kablolamasi (composition root).
Calistirma: python -m app.main

Faz 1 kablolamasi:
- STATE_BACKEND=sqlite -> cooldown/sonuclar DB'de (Render free'de disk ephemeral)
- yfinance (tarihsel) + Finnhub (earnings takvimi; quote Phase 2)
- Evren: Midas scrape -> cache -> statik yedek zinciri + likidite filtresi
Faz 3 aktif: shadow tracking (SHADOW_TRACKING), gist yedekleme (GITHUB_TOKEN
+ GIST_SYNC), /dashboard izleme ekrani.
"""
from __future__ import annotations

import logging
import os

from app.config.settings import get_settings
from app.integrations.finnhub_client import FinnhubClient
from app.integrations.gist_client import GistClient
from app.integrations.telegram_notifier import TelegramNotifier
from app.integrations.yfinance_client import YFinanceClient
from app.logging_setup import kv, setup_logging
from app.scheduler import Scheduler
from app.server import create_app
from app.services.database import Database
from app.services.commentary import CommentaryService
from app.services.earnings_service import EarningsService
from app.services.gist_backup import GistBackup
from app.services.market_calendar import MarketCalendar
from app.services.news_service import NewsService
from app.services.market_data_service import MarketDataService
from app.services.signal_tracker import SignalTracker
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
    db = Database(settings.DB_PATH)
    if settings.STATE_BACKEND.lower() == "sqlite":
        store = SQLiteStateStore(db)
    else:
        store = InMemoryStateStore()

    # --- veri katmani (iki kaynakli) ---
    yf_client = YFinanceClient(settings.YF_CHUNK_SIZE, settings.YF_CHUNK_PAUSE_SEC,
                               settings.YF_MAX_RETRIES, settings.YF_BACKOFF_SEC)
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

    # --- golge takip (Faz 3): sessiz performans muhasebesi + veri arsivi ---
    tracker = None
    if settings.SHADOW_TRACKING:
        tracker = SignalTracker(db, settings.MTF,
                                settings.FILL_WINDOW_BARS,
                                settings.MAX_TRACK_BARS)

    # --- haber akisi (dashboard beslemesi; Finnhub gerektirir) ---
    news = None
    if settings.FINNHUB_API_KEY:
        news = NewsService(finnhub, settings.NEWS_REFRESH_SEC,
                           settings.NEWS_MAX_SYMBOLS, settings.NEWS_KEEP)

    # --- otomatik degerlendirme (bybit botundaki commentary uyarlamasi) ---
    commentary = None
    if tracker is not None:
        commentary = CommentaryService(db, tracker,
                                       settings.COMMENT_INTERVAL_SEC)

    # --- gist yedekleme: botun kendi kayit tutma mekanizmasi ---
    gist_backup = None
    if settings.GIST_SYNC and settings.GITHUB_TOKEN and tracker is not None:
        gist_backup = GistBackup(
            GistClient(settings.GITHUB_TOKEN), tracker,
            sync_interval_sec=settings.GIST_SYNC_INTERVAL_SEC,
            pinned_gist_id=settings.GIST_ID,
            candle_mode=settings.GIST_CANDLE_MODE,
            candle_max_rows=settings.GIST_CANDLE_MAX_ROWS,
            meta_provider=lambda: {"universe": universe.describe()},
            commentary_provider=(commentary.recent if commentary else None))
        try:
            gist_backup.restore_if_empty()  # redeploy sonrasi self-healing
        except Exception:
            log.exception(kv(event="gist_restore_error"))
    elif settings.GIST_SYNC and not settings.GITHUB_TOKEN:
        log.warning(kv(event="gist_env_missing",
                       note="GITHUB_TOKEN yok; yedekleme kapali, veri restart'ta silinir"))

    scheduler = Scheduler(settings, market_data, universe, earnings,
                          calendar, store, notifier, tracker, gist_backup,
                          commentary, news)
    app = create_app(store, scheduler, universe, tracker, gist_backup,
                     commentary, news)

    scheduler.start_background()
    port = int(os.getenv("PORT", "10000"))
    log.info(kv(event="server_start", port=port,
                state_backend=settings.STATE_BACKEND,
                universe_source=settings.UNIVERSE_SOURCE,
                shadow=tracker is not None, gist=gist_backup is not None))
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
