"""Alpaca KAGIT hesap emir istemcisi - AYNA adim 3 (v4.32, 13 Agu 2026).

app/services/alpaca_mirror.py docstring'indeki ISTEMCI SOZLESMESI'nin
canli uygulamasi. Ilke ayni: INCE TRANSKRIPSIYON - broker ne diyorsa o;
simulasyon, tahmin, fiyat uydurma YOK (anayasa 2.1).

GUVENLIK KILIDI: base_url icinde 'paper' gecmek ZORUNDA. Bu istemci
gercek-para ucuna (api.alpaca.markets) BILEREK baglanamaz - yanlis env,
yanlis kopyala-yapistir, ileride 'canliya cevirelim' hevesi: hepsi
kurulusta ValueError ile durur. Gercek para karari ayri bir tasarim ve
Serhat onayi ister; bu dosyada acilan bir kapi DEGILDIR.

Broker kisitlari (13 Agu itibariyla dokumante):
- Bracket (OCO) emirlerde KESIRLI adet desteklenmez -> qty tam sayiya
  yuvarlanir (min 1). Ayna olcumu dolum orani/fiyati pesindedir, P&L
  buyuklugu degil; kucuk sapma kabul edilir ve qty ayna tablosunda durur.
- close_position piyasa emri ACIKTA hemen dolmayabilir (seans disi
  time-stop tetigi kuyruga girer) -> fiyat henuz yoksa None doner,
  transkripsiyon ilkesi geregi uydurulmaz.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime

import requests

from app.logging_setup import kv

log = logging.getLogger("alpaca_paper")

_PAPER_BASE = "https://paper-api.alpaca.markets"


def _to_epoch_ms(ts: str | None) -> int | None:
    """RFC3339 ('2026-08-13T14:30:05.123456789Z') -> epoch ms. Saf.
    Alpaca nanosaniye verir; fromisoformat (3.10) en cok 6 hane kabul
    eder -> kesir 6 haneye kirpilir."""
    if not ts:
        return None
    try:
        s = ts.replace("Z", "+00:00")
        m = re.match(r"^(.*?T[\d:]+)(\.(\d+))?([+-]\d{2}:\d{2})$", s)
        if m:
            frac = f".{(m.group(3) or '0')[:6]}"
            s = f"{m.group(1)}{frac}{m.group(4)}"
        return int(datetime.fromisoformat(s).timestamp() * 1000)
    except (ValueError, TypeError):
        return None


class AlpacaPaperClient:
    """Emir yetkili KAGIT hesap istemcisi (sozlesme: alpaca_mirror)."""

    def __init__(self, api_key: str, api_secret: str,
                 base_url: str = _PAPER_BASE, timeout: float = 20.0) -> None:
        if "paper" not in (base_url or ""):
            raise ValueError(
                "AlpacaPaperClient yalniz KAGIT hesaba baglanir; "
                f"verilen adres reddedildi: {base_url!r}")
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._headers = {"APCA-API-KEY-ID": api_key,
                         "APCA-API-SECRET-KEY": api_secret}

    # ------------------------------------------------------------ yardimci
    def _req(self, method: str, path: str, **kw):
        try:
            r = requests.request(method, f"{self._base}{path}",
                                 headers=self._headers,
                                 timeout=self._timeout, **kw)
            if r.status_code in (200, 201, 204, 207):
                return r
            log.warning(kv(event="alpaca_paper_http", path=path,
                           status=r.status_code, body=r.text[:200]))
        except requests.RequestException as e:
            log.warning(kv(event="alpaca_paper_error", path=path,
                           error=repr(e)))
        return None

    # ------------------------------------------------------------ sozlesme
    def submit_bracket(self, symbol: str, side: str, qty: float,
                       limit_price: float, stop_price: float,
                       tp_price: float) -> str | None:
        qty_int = max(1, int(round(qty)))     # bracket kesirli adet almaz
        payload = {
            "symbol": symbol, "side": side, "qty": str(qty_int),
            "type": "limit", "limit_price": str(round(limit_price, 2)),
            # gtc: dolum penceresi ~2 seans; day emri ilk kapanista duserdi
            # ve pencere iptalini ayna zaten 14 kapanmis barda kendi verir
            "time_in_force": "gtc", "order_class": "bracket",
            "take_profit": {"limit_price": str(round(tp_price, 2))},
            "stop_loss": {"stop_price": str(round(stop_price, 2))},
        }
        r = self._req("POST", "/v2/orders", json=payload)
        if r is None:
            return None
        oid = (r.json() or {}).get("id")
        log.info(kv(event="alpaca_paper_submit", symbol=symbol,
                    side=side, qty=qty_int, order_id=oid))
        return oid

    def order_status(self, order_id: str) -> dict | None:
        r = self._req("GET", f"/v2/orders/{order_id}", params={"nested": "true"})
        if r is None:
            return None
        o = r.json() or {}
        status = o.get("status")
        fill_price = float(o["filled_avg_price"]) if o.get("filled_avg_price") else None
        fill_ts = _to_epoch_ms(o.get("filled_at"))
        # bracket bacaklari: cikis, bacaklardan birinin dolmasidir
        for leg in o.get("legs") or []:
            if leg.get("status") == "filled":
                return {"status": "closed", "fill_price": fill_price,
                        "fill_ts": fill_ts,
                        "exit_price": float(leg["filled_avg_price"])
                        if leg.get("filled_avg_price") else None,
                        "exit_ts": _to_epoch_ms(leg.get("filled_at")),
                        "exit_reason": "STOP"
                        if "stop" in (leg.get("type") or "") else "TP"}
        if status == "filled":
            return {"status": "filled", "fill_price": fill_price,
                    "fill_ts": fill_ts, "exit_price": None,
                    "exit_ts": None, "exit_reason": None}
        if status in ("canceled", "expired", "rejected", "replaced"):
            return {"status": "canceled", "fill_price": None, "fill_ts": None,
                    "exit_price": None, "exit_ts": None, "exit_reason": None}
        return {"status": "new", "fill_price": None, "fill_ts": None,
                "exit_price": None, "exit_ts": None, "exit_reason": None}

    def cancel(self, order_id: str) -> bool:
        return self._req("DELETE", f"/v2/orders/{order_id}") is not None

    def close_position(self, symbol: str, qty: float | None = None) -> dict | None:
        """Pozisyonu piyasa emriyle kapat (time-stop). Kapanis emri hemen
        dolmadiysa fiyat UYDURULMAZ (None doner); ayna CLOSED/TIME yazar,
        fiyati bos kalir - transkripsiyon ilkesi."""
        r = self._req("DELETE", f"/v2/positions/{symbol}")
        if r is None:
            return None
        o = r.json() or {}
        oid = o.get("id")
        if oid:                               # emri bir kez yokla (uyumadan)
            st = self.order_status(oid) or {}
            if st.get("status") == "filled":
                return {"price": st.get("fill_price"), "ts": st.get("fill_ts")}
        return {"price": None, "ts": None}
