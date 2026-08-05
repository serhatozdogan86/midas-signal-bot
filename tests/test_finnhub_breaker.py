"""v4.7: saglayici arizasinda gurultu ve bosuna deneme olmasin.

4 Agu gecesi Finnhub /quote 502 dondu; tek kesintide 30 ERROR satiri
dustu. Yedegimiz (Alpaca) devredeydi, yani bu bizim hatamiz DEGILDI -
ama gercek bir sorun o gurultunun icinde kaybolurdu.
"""
from __future__ import annotations

import time

from app.integrations.finnhub_client import FinnhubClient


class _Resp:
    def __init__(self, status):
        self.status_code = status

    def json(self):
        return {"c": 1.0}


class _Session:
    def __init__(self, status):
        self.status = status
        self.calls = 0

    def get(self, *a, **k):
        self.calls += 1
        return _Resp(self.status)


def _client(status):
    c = FinnhubClient("key", "https://x.test")
    c._session = _Session(status)
    return c


def test_provider_5xx_is_warning_not_error(caplog):
    c = _client(502)
    with caplog.at_level("WARNING"):
        assert c._get("/quote", {}) is None
    msgs = " ".join(r.message for r in caplog.records)
    assert "finnhub_provider_down" in msgs
    assert "finnhub_http_error" not in msgs      # ERROR seviyesi DEGIL
    assert not any(r.levelname == "ERROR" for r in caplog.records)


def test_client_4xx_stays_error(caplog):
    """Yanlis anahtar/istek BIZIM hatamizdir - ERROR kalmali."""
    c = _client(401)
    with caplog.at_level("WARNING"):
        c._get("/quote", {})
    assert any(r.levelname == "ERROR" for r in caplog.records)


def test_breaker_opens_after_repeated_failures():
    c = _client(503)
    for _ in range(5):
        c._get("/quote", {})
    assert c.breaker_open() is True
    before = c._session.calls
    for _ in range(10):
        assert c._get("/quote", {}) is None
    assert c._session.calls == before          # bosuna deneme YOK


def test_breaker_resets_after_success():
    c = _client(503)
    for _ in range(5):
        c._get("/quote", {})
    assert c.breaker_open()
    c._blocked_until = time.time() - 1         # sure doldu
    c._session.status = 200
    assert c._get("/quote", {}) == {"c": 1.0}
    assert c.breaker_open() is False and c._fail_count == 0
