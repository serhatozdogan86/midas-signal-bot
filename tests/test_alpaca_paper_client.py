"""v4.32 AYNA adim 3: canli KAGIT istemcisi - HTTP sahteleyerek.

Gercek aga cikilmaz; requests.request monkeypatch'lenir. Sozlesme
alpaca_mirror docstring'indeki ISTEMCI SOZLESMESI'dir - FakeClient'la
ayni sekil, ayni alanlar.
"""
from __future__ import annotations

import pytest

from app.integrations import alpaca_paper_client as apc
from app.integrations.alpaca_paper_client import AlpacaPaperClient, _to_epoch_ms


class _Resp:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self._body = body or {}
        self.text = str(body)

    def json(self):
        return self._body


def _client(monkeypatch, responses):
    """responses: (method, path_parcasi) -> _Resp listesi (sirali tuketilir)."""
    calls = []

    def fake_request(method, url, **kw):
        calls.append((method, url, kw))
        for i, (m, frag, resp) in enumerate(responses):
            if m == method and frag in url:
                responses.pop(i)
                return resp
        return _Resp(404, {})

    monkeypatch.setattr(apc.requests, "request", fake_request)
    return AlpacaPaperClient("k", "s"), calls


def test_paper_disi_adres_kurulusta_reddedilir():
    """GUVENLIK KILIDI: gercek-para ucuna baglanmak MUMKUN OLMAMALI.
    Bu test kirilirsa kilit sokulmus demektir - v4.32 sozlesmesi."""
    with pytest.raises(ValueError):
        AlpacaPaperClient("k", "s", base_url="https://api.alpaca.markets")
    AlpacaPaperClient("k", "s")                # varsayilan paper: sorunsuz


def test_submit_bracket_govdesi_ve_tam_sayi_adet(monkeypatch):
    cli, calls = _client(monkeypatch, [
        ("POST", "/v2/orders", _Resp(200, {"id": "oid-1"}))])
    oid = cli.submit_bracket("DAL", "buy", 12.3456, 87.015, 84.0, 90.0)
    assert oid == "oid-1"
    body = calls[0][2]["json"]
    assert body["qty"] == "12"                 # bracket kesirli adet almaz
    assert body["order_class"] == "bracket"
    assert body["time_in_force"] == "gtc"
    assert body["take_profit"]["limit_price"] == "90.0"
    assert body["stop_loss"]["stop_price"] == "84.0"
    # 100$/risk cok kucuk adet verse bile min 1 (olcum devam etmeli)
    cli2, calls2 = _client(monkeypatch, [
        ("POST", "/v2/orders", _Resp(200, {"id": "oid-2"}))])
    cli2.submit_bracket("BKNG", "buy", 0.02, 4000.0, 3900.0, 4200.0)
    assert calls2[0][2]["json"]["qty"] == "1"


def test_order_status_dolum_ve_bacak_cikisi(monkeypatch):
    filled = {"status": "filled", "filled_avg_price": "87.01",
              "filled_at": "2026-08-13T14:30:05.123456789Z", "legs": [
                  {"status": "new", "type": "limit"},
                  {"status": "new", "type": "stop"}]}
    cli, _ = _client(monkeypatch, [("GET", "/v2/orders/o1", _Resp(200, filled))])
    st = cli.order_status("o1")
    assert st["status"] == "filled" and st["fill_price"] == 87.01
    assert st["fill_ts"] and st["exit_reason"] is None

    closed = dict(filled)
    closed["legs"] = [
        {"status": "filled", "type": "stop", "filled_avg_price": "84.0",
         "filled_at": "2026-08-14T15:00:00Z"},
        {"status": "canceled", "type": "limit"}]
    cli2, _ = _client(monkeypatch, [("GET", "/v2/orders/o1", _Resp(200, closed))])
    st2 = cli2.order_status("o1")
    assert st2["status"] == "closed"
    assert st2["exit_reason"] == "STOP" and st2["exit_price"] == 84.0

    cli3, _ = _client(monkeypatch, [
        ("GET", "/v2/orders/o1", _Resp(200, {"status": "canceled"}))])
    assert cli3.order_status("o1")["status"] == "canceled"


def test_cancel_ve_close_position(monkeypatch):
    cli, _ = _client(monkeypatch, [("DELETE", "/v2/orders/o1", _Resp(204))])
    assert cli.cancel("o1") is True

    # kapanis emri hemen dolmadi -> fiyat UYDURULMAZ (None)
    cli2, _ = _client(monkeypatch, [
        ("DELETE", "/v2/positions/DAL", _Resp(200, {"id": "c1"})),
        ("GET", "/v2/orders/c1", _Resp(200, {"status": "new"}))])
    res = cli2.close_position("DAL")
    assert res == {"price": None, "ts": None}

    # dolduysa broker fiyati aynen gecer
    cli3, _ = _client(monkeypatch, [
        ("DELETE", "/v2/positions/DAL", _Resp(200, {"id": "c2"})),
        ("GET", "/v2/orders/c2", _Resp(200, {
            "status": "filled", "filled_avg_price": "88.4",
            "filled_at": "2026-08-14T20:00:00Z"}))])
    assert cli3.close_position("DAL")["price"] == 88.4


def test_epoch_donusumu_nanosaniyeyi_sindirir():
    assert _to_epoch_ms("2026-08-13T14:30:05.123456789Z") == _to_epoch_ms(
        "2026-08-13T14:30:05.123456Z")
    assert _to_epoch_ms("2026-08-13T14:30:05Z") is not None
    assert _to_epoch_ms(None) is None and _to_epoch_ms("bozuk") is None
