"""v4.13: dead-man alarmi yeniden baslamada YANLIS otmemeli.

5 Agu vakasi: servis seans ortasinda yeniden basladi (14:03), alarm
14:13'te otti, ilk tarama 14:13:49'da tamamlandi. last_scan_info
BELLEKTE tutuldugu icin restart sonrasi "hic tarama yok" gorunuyor -
oysa hazirlik + ilk tarama ~10 dk surer. Yanlis alarm, alarmin
degerini dusurur; gercek arizada "yine mi" denir.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from app.scheduler import Scheduler


class _S:
    DEADMAN_SCAN_STALENESS_MIN = 25


class _N:
    def __init__(self):
        self.sent = []
        self.configured = True

    def send(self, t):
        self.sent.append(t)
        return True


def _sched(uptime_min):
    s = object.__new__(Scheduler)
    s._settings = _S()
    s._notifier = _N()
    s._settings.TELEGRAM_ALERTS_ENABLED = True
    s._tg_muted = s._tg_fail = 0
    s._tg_last_ok = 0.0
    s._deadman_date = None
    s.last_scan_info = {}
    s._started_at = time.time() - uptime_min * 60
    return s


def _times(minutes_open=60):
    now = datetime.now(timezone.utc)
    return now, now - timedelta(minutes=minutes_open), now.date()


def test_no_alert_during_warmup_after_restart():
    s = _sched(uptime_min=10)          # yeni basladi
    now, open_dt, today = _times()
    s._deadman_check(now, open_dt, today)
    assert s._notifier.sent == []      # ALARM YOK
    assert s._deadman_date is None     # gun de isaretlenmedi


def test_alert_fires_when_loop_really_stuck():
    s = _sched(uptime_min=90)          # uzun suredir ayakta, tarama yok
    now, open_dt, today = _times()
    s._deadman_check(now, open_dt, today)
    assert len(s._notifier.sent) == 1
    assert "DEAD-MAN" in s._notifier.sent[0]
    assert "dk'dir ayakta" in s._notifier.sent[0]   # teshis icin uptime


def test_fresh_scan_silences_alarm():
    s = _sched(uptime_min=90)
    s.last_scan_info = {"ts_utc": datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")}
    now, open_dt, today = _times()
    s._deadman_check(now, open_dt, today)
    assert s._notifier.sent == []


def test_alert_only_once_per_day():
    s = _sched(uptime_min=90)
    now, open_dt, today = _times()
    s._deadman_check(now, open_dt, today)
    s._deadman_check(now, open_dt, today)
    assert len(s._notifier.sent) == 1
