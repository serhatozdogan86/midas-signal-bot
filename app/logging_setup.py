"""Structured logging - tek satir, sabit alan sirasi: ts | level | module | mesaj.
Ek: RingBufferHandler - son WARNING/ERROR kayitlarini bellekte tutar; /diag ucu
ve dashboard'a gomulu server-diag blogu buradan beslenir (uzaktan tani icin -
Render log konsoluna girmeden botun sagligini disaridan okuma imkani).
"""
from __future__ import annotations

import logging
import time
from collections import deque
from datetime import datetime, timezone


class RingBufferHandler(logging.Handler):
    """Son N WARNING+ log kaydini bellekte tutar (restart'ta sifirlanir)."""

    def __init__(self, maxlen: int = 300) -> None:
        super().__init__(level=logging.WARNING)
        self.records: deque = deque(maxlen=maxlen)
        self.counts = {"WARNING": 0, "ERROR": 0}
        self.started_at = time.time()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
            if record.exc_info and record.exc_info[1] is not None:
                msg += f" | exc={record.exc_info[0].__name__}: {record.exc_info[1]}"
            self.records.append({
                "ts": datetime.fromtimestamp(
                    record.created, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "level": record.levelname,
                "logger": record.name,
                "msg": msg[:250],
            })
            key = "ERROR" if record.levelno >= logging.ERROR else "WARNING"
            self.counts[key] += 1
        except Exception:  # log handler asla patlatmaz
            pass

    def recent(self, n: int = 60) -> list[dict]:
        return list(self.records)[-n:]

    def uptime_sec(self) -> int:
        return int(time.time() - self.started_at)


_ring: RingBufferHandler | None = None


def get_ring_buffer() -> RingBufferHandler:
    global _ring
    if _ring is None:
        _ring = RingBufferHandler()
        logging.getLogger().addHandler(_ring)
    return _ring


def _silence_noisy_libs() -> None:
    """yfinance sembol-basi ERROR satirlari basar (rate-limit/delisted);
    bunlar bizim hata sayacimizi kirletiyordu. Kutuphane logger'i
    susturulur - toplu basarisizliklar zaten kendi kodumuzda loglanir."""
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    # Gurultulu kutuphaneleri kis
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("yfinance").setLevel(logging.WARNING)
    logging.getLogger("peewee").setLevel(logging.WARNING)
    get_ring_buffer()  # WARNING+ kayitlari /diag icin biriktir


def kv(**fields: object) -> str:
    """key=value log yardimcisi: log.info(kv(symbol=s, decision=d))"""
    return " ".join(f"{k}={v}" for k, v in fields.items())
