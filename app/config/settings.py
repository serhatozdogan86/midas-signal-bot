"""
Config loader - tum ayarlar env'den, tipli ve dogrulanmis.
Engine katmanina Settings degil StrategyParams enjekte edilir (saf/test edilebilir).
Env adlari plan dokumani bolum 8 ile birebir uyumludur.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class StrategyParams(BaseModel):
    """Signal engine'in ihtiyac duydugu tum esikler. Engine'e bagimlilik olarak gecer."""

    htf: str = "1d"                  # rejim/yon zaman dilimi
    mtf: str = "1h"                  # setup/yapi zaman dilimi
    min_bars_daily: int = 210        # SMA200 + pivotlar icin asgari gunluk bar
    min_bars_hourly: int = 60

    # Trend / yapi
    pivot_lookback: int = 3
    ema_slope_bars: int = 10         # 1h EMA20 egim kontrolu (kac bar oncesiyle)
    pullback_window: int = 8         # pullback kosullarinin aranacagi son bar sayisi
    pullback_touch_tol: float = 0.003
    rsi3_oversold: float = 20.0
    rsi3_overbought: float = 80.0
    stop_lookback_bars: int = 16     # yapisal stop icin son N 1h bar

    # Hacim
    volume_mult: float = 1.3         # tetik mumu rel. hacim esigi (1h, SMA20'ye gore)

    # Risk / hedef (gunluk ATR bazli - plan bolum 2)
    atr_tp1_mult: float = 1.0
    atr_tp2_mult: float = 2.0
    atr_stop_mult: float = 1.2       # stop mesafesi ust siniri (gunluk ATR carpani)
    min_rr: float = 2.0              # RR = (TP2 - entry) / risk  (tasarim notu: README)
    min_target_pct: float = 2.0      # maliyet filtresi: TP1 mesafesi >= %2 (1.5$/islem)

    # Earnings / zaman
    earnings_blackout_days: int = 2  # bilancoya +-N islem gunu -> sinyal yok
    time_stop_days: int = 4

    # Short asimetrisi + NEUTRAL rejim sikilastirmasi (plan bolum 4)
    short_enabled: bool = True
    short_requires_weak_rs: bool = True
    neutral_rr_bump: float = 0.5     # NEUTRAL rejimde min_rr'a eklenir
    neutral_volume_bump: float = 0.2 # NEUTRAL rejimde volume_mult'a eklenir

    # Confluence esikleri
    rs_lookback_days: int = 63
    near_high_pct: float = 5.0       # 52H zirveye <= %5 -> confluence


class Settings(BaseSettings):
    """Env degiskenleri. Alan adi == env adi (plan bolum 8)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Telegram
    TELEGRAM_ENABLED: bool = True
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    TELEGRAM_PARSE_MODE: str = ""    # "" (plain) | MarkdownV2 (Phase 3)

    # Finnhub (quote Phase 2, earnings takvimi Phase 1)
    FINNHUB_API_KEY: str = ""
    FINNHUB_BASE_URL: str = "https://finnhub.io/api/v1"

    # Evren
    UNIVERSE_SOURCE: str = "midas"           # midas | static
    MIDAS_UNIVERSE_URL: str = "https://www.getmidas.com/amerikan-borsasi/"
    STATIC_UNIVERSE_PATH: str = "data/static_universe.txt"
    UNIVERSE_CACHE_PATH: str = "data/universe_cache.json"
    UNIVERSE_MIN_DOLLAR_VOL: float = 5_000_000
    UNIVERSE_MIN_PRICE: float = 3.0
    UNIVERSE_MIN_EXPECTED: int = 50          # scrape bundan az sembol dondururse basarisiz say
    UNIVERSE_MAX_SYMBOLS: int = 300          # yfinance yuku icin ust sinir

    # Tarama ritmi (plan bolum 5)
    COARSE_SCAN_INTERVAL_SEC: int = 900      # 15 dk kaba tarama
    FINE_SCAN_INTERVAL_SEC: int = 60         # Phase 2 (rezerve)
    WATCHLIST_MAX: int = 40
    PREP_LEAD_MIN: int = 45                  # acilistan once hazirlik (08:45 ET ~ 15:45 TR)
    EOD_DELAY_MIN: int = 15                  # kapanistan sonra ozet (16:15 ET ~ 23:15 TR)
    LOOP_TICK_SEC: int = 20

    # Zaman dilimleri
    HTF: str = "1d"
    MTF: str = "1h"
    DAILY_PERIOD: str = "2y"                 # yfinance period (SMA200 + 52H icin)
    HOURLY_PERIOD: str = "60d"

    # Strateji esikleri
    ATR_TP1_MULT: float = 1.0
    ATR_TP2_MULT: float = 2.0
    ATR_STOP_MULT: float = 1.2
    RISK_REWARD_MIN: float = 2.0
    MIN_TARGET_PCT: float = 2.0
    VOLUME_MULT: float = 1.3
    EARNINGS_BLACKOUT_DAYS: int = 2
    TIME_STOP_DAYS: int = 4
    SHORT_ENABLED: bool = True

    # Endeks rejim sembolleri
    REGIME_SYMBOLS: str = "SPY,QQQ"

    # Davranis
    SEND_NO_TRADE: bool = False
    SEND_PREP_SUMMARY: bool = True
    SEND_EOD_SUMMARY: bool = True
    SIGNAL_COOLDOWN_SEC: int = 86400
    LOG_LEVEL: str = "INFO"

    # yfinance toplu indirme
    YF_CHUNK_SIZE: int = 50
    YF_CHUNK_PAUSE_SEC: float = 1.0

    # Kalicilik
    DB_PATH: str = "data/bot.db"
    STATE_BACKEND: str = "sqlite"            # sqlite | memory

    # Phase 3 rezervleri (gist yedekleme) - kablolama Phase 3'te
    GITHUB_TOKEN: str = ""
    GIST_SYNC: bool = True
    GIST_ID: str = ""                      # bos = MARKER ile otomatik bul/olustur
    GIST_SYNC_INTERVAL_SEC: int = 3600
    GIST_CANDLE_MODE: str = "signals"      # signals | all | off
    GIST_CANDLE_MAX_ROWS: int = 3000

    # Golge takip (shadow tracking - sessiz performans muhasebesi)
    SHADOW_TRACKING: bool = True
    FILL_WINDOW_BARS: int = 14             # girise gelmesi beklenen sure (~2 seans, 1h bar)
    MAX_TRACK_BARS: int = 28               # dolduysa izleme suresi (~4 seans = time-stop)

    @property
    def regime_symbols(self) -> list[str]:
        return [s.strip().upper() for s in self.REGIME_SYMBOLS.split(",") if s.strip()]

    @property
    def strategy_params(self) -> StrategyParams:
        return StrategyParams(
            htf=self.HTF,
            mtf=self.MTF,
            atr_tp1_mult=self.ATR_TP1_MULT,
            atr_tp2_mult=self.ATR_TP2_MULT,
            atr_stop_mult=self.ATR_STOP_MULT,
            min_rr=self.RISK_REWARD_MIN,
            min_target_pct=self.MIN_TARGET_PCT,
            volume_mult=self.VOLUME_MULT,
            earnings_blackout_days=self.EARNINGS_BLACKOUT_DAYS,
            time_stop_days=self.TIME_STOP_DAYS,
            short_enabled=self.SHORT_ENABLED,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
