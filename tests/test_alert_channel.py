"""v4.9: uyarilar ve sinyaller AYRI kanal.

Golge modda sinyal gurultusu istemiyoruz ama kritik uyarilari
istiyoruz. Bu ayrimin gercekten calistigi burada kilitlenir.
"""
from __future__ import annotations

from app.scheduler import Scheduler


class _Notifier:
    def __init__(self, ok=True):
        self.sent = []
        self.ok = ok
        self.configured = True

    def send(self, text):
        self.sent.append(text)
        return self.ok


class _S:
    TELEGRAM_ENABLED = False
    TELEGRAM_ALERTS_ENABLED = True


def _sched(signals_on=False, alerts_on=True, ok=True):
    s = object.__new__(Scheduler)
    st = _S()
    st.TELEGRAM_ENABLED = signals_on
    st.TELEGRAM_ALERTS_ENABLED = alerts_on
    s._settings = st
    s._notifier = _Notifier(ok)
    s._tg_muted = 0
    s._tg_fail = 0
    s._tg_last_ok = 0.0
    return s


def test_alerts_go_out_while_signals_are_muted():
    s = _sched(signals_on=False, alerts_on=True)
    assert s._send("SINYAL | AAPL LONG") is False        # susturuldu
    assert s._send_alert("UYARI: bilanco takvimi yok") is True
    assert s._notifier.sent == ["UYARI: bilanco takvimi yok"]
    assert s._tg_muted == 1


def test_alerts_can_be_muted_too_but_counted():
    s = _sched(signals_on=False, alerts_on=False)
    assert s._send_alert("UYARI") is False
    assert s._notifier.sent == []
    assert s._tg_muted == 1


def test_failed_send_is_counted_not_swallowed():
    s = _sched(alerts_on=True, ok=False)
    assert s._send_alert("UYARI") is False
    assert s._tg_fail == 1
    assert s.telegram_status()["failed"] == 1


def test_status_reports_channel_state():
    s = _sched(signals_on=False, alerts_on=True)
    s._send_alert("x")
    st = s.telegram_status()
    assert st["configured"] and st["alerts_on"] and st["signals_on"] is False
    assert st["last_ok_age_min"] == 0
