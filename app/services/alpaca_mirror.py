"""ALPACA AYNA KATMANI - ADIM 1, iskelet (v4.19): golge defterin dolum
varsayimlarini Alpaca KAGIT hesabiyla bagimsiz dogrulama programi.
SALT OLCUM - karara, portfoy tavanlarina, karneye ve go-live sayacina
KARISMAZ (v3.19 exit_lab emsali; kilit ihlali degildir).

NEDEN (7 Agu tasarim karari, docs/config-lock.md): defterin tum R
muhasebesi simule dolum varsayimlarina dayanir (bolgenin tam katedilmesi,
5bp cikis kaymasi, gap'te acilis fiyati). 60 islemlik kohorttan verilecek
her karar (go-live, V0/V1/V2/V3, short) ayni varsayimlara dayanacak; ayna
bu varsayimlari gercek(imsi) emir mekanigiyle test eder. NOT: Alpaca
paper da bir simulasyondur (NBBO dokununca dolum varsayar) - mutlak
gercek DEGIL, bagimsiz ikinci gorus olarak okunur.

IZOLASYON SOZLESMESI (tests/test_alpaca_mirror.py ile kilitli):
1. Karar modulleri (app/strategies/*, signal_tracker) bu modulu IMPORT
   EDEMEZ (AST testi). Yalniz scheduler (orkestrasyon) cagirabilir.
2. Ayna KENDI tablosuna yazar (mirror_fills); signals tablosuna alan
   EKLENMEZ. Defter aynayi hic okumaz - veri akisi tek yonlu:
   signals (salt okunur) -> mirror_fills -> rapor/diag.
3. self_audit 13. degismez ("ayna izolasyonu") sema ayrikligini CANLIDA
   surekli izler (signals icinde mirror/alpaca alani = ihlal).
4. Ayna ciktilari yalniz "AYNA - karara girmez" etiketiyle raporlanir.
5. Sapma bulgusu OTOMATIK hicbir esigi degistirmez; config-lock surecine
   (olc -> gerekce -> onay -> yeni kilit) girdi olur.

ADIM 2 (v4.24, Serhat onayi 8 Agu): emir yasam dongusu - istemci
arayuzu uzerinden limit+bracket gonderimi, dolum/cikis TRANSKRIPSIYONU,
14 barlik pencere iptali (canli FILL_WINDOW_BARS ile birebir - onerilen
secim), 28 barlik time-stop kapamasi. SHORT'lar da aynalanir (onerilen
secim: kapatma karari gelirse elde bagimsiz veri olur). Istemci step
2'de SAHTE (testlerde); ALPACA_MIRROR_ENABLED varsayilan False kalir.
Adim 3: canli paper istemcisi + 2 hafta alarmsiz izleme. Adim 4: sapma
esikleri OLCUMDEN ONCE yazilir, EOD raporuna AYNA bolumu.

ISTEMCI SOZLESMESI (adim 3'un uygulayacagi arayuz):
  submit_bracket(symbol, side, qty, limit_price, stop_price, tp_price)
      -> order_id | None       (side: 'buy' | 'sell')
  order_status(order_id) -> dict | None
      {'status': 'new'|'filled'|'closed'|'canceled',
       'fill_price': float|None, 'fill_ts': int|None,
       'exit_price': float|None, 'exit_ts': int|None,
       'exit_reason': 'STOP'|'TP'|None}
  cancel(order_id) -> bool
  close_position(symbol, qty) -> dict | None   ({'price':..,'ts':..})
Ayna mantigi bilerek INCE tutulur: broker'in soyledigini mirror_fills'e
yazar, pencere/time-stop tetiklerini kosar - simulasyon YAPMAZ (o isi
tracker yapiyor; ayna tam da onu dogrulamak icin var).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.logging_setup import kv

log = logging.getLogger("alpaca_mirror")

# Ayna verisi YALNIZ bu tabloda yasar (izolasyon sozlesmesi md. 2).
_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS mirror_fills(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  signal_id INTEGER NOT NULL,
  symbol TEXT NOT NULL, direction TEXT NOT NULL,
  created_utc TEXT NOT NULL,
  entry_min REAL, entry_max REAL, stop_loss REAL, tp1 REAL,
  alpaca_order_id TEXT,
  alpaca_status TEXT NOT NULL DEFAULT 'INTENT',
  alpaca_fill_price REAL, alpaca_exit_price REAL,
  note TEXT
)
"""
_INDEX_SQL = ("CREATE UNIQUE INDEX IF NOT EXISTS idx_mirror_signal "
              "ON mirror_fills(signal_id)")


REF_RISK_USD = 100.0        # tracker.cost_r ile ayni referans (10k$ / %1)
FILL_WINDOW_BARS = 14       # canli defterle birebir (FILL_WINDOW_BARS)
MAX_TRACK_BARS = 28         # canli time-stop ile birebir (MAX_TRACK_BARS)


class AlpacaMirror:
    """Adim 2: niyet + emir yasam dongusu (istemci arayuzu uzerinden).

    db: services.database.Database (signals ile ayni dosya, AYRI tablo -
    ayrikligi tablo duzeyinde tutmak, gist yedeklemesinin aynayi da
    kapsamasini bedavaya getirir).
    """

    def __init__(self, db, enabled: bool = False, client=None,
                 fill_window: int = FILL_WINDOW_BARS,
                 max_track: int = MAX_TRACK_BARS) -> None:
        self._db = db
        self._enabled = bool(enabled)
        self._client = client          # adim 3: emir yetkili alpaca istemcisi
        self._fill_window = fill_window
        self._max_track = max_track
        self._gaps = 0                 # aynalanamayan sinyal sayaci (fail-open gorunurlugu)
        db.execute(_TABLE_SQL)
        db.execute(_INDEX_SQL)
        # adim 2 kolonlari - eski iskeletten kalan tablolara guvenle eklenir
        for col in ("qty REAL", "entry_candle_ts INTEGER",
                    "alpaca_fill_ts INTEGER", "alpaca_exit_ts INTEGER",
                    "closed_reason TEXT"):
            try:
                db.execute(f"ALTER TABLE mirror_fills ADD COLUMN {col}")
            except Exception:
                pass

    @property
    def enabled(self) -> bool:
        return self._enabled

    def record_intent(self, signal_row: dict) -> bool:
        """Deftere giren (blocked=0) sinyalin ayna NIYETINI kaydet.

        signal_row: tracker'in signals tablosundan SALT OKUNUR satir.
        Donus: kayit acildiysa True; kapali/mukerrer ise False.
        Ayna olcum katmanidir: hata durumunda motoru ASLA etkilemez
        (fail-open) ama bosluk sessiz kalmaz - _gaps sayaci diag'da okunur.
        """
        if not self._enabled:
            return False
        try:
            sid = int(signal_row["id"])
            if self._db.query_one(
                    "SELECT id FROM mirror_fills WHERE signal_id=?", (sid,)):
                return False
            self._db.execute(
                "INSERT INTO mirror_fills(signal_id, symbol, direction, "
                "created_utc, entry_min, entry_max, stop_loss, tp1) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (sid, signal_row["symbol"], signal_row["direction"],
                 datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 signal_row.get("entry_min"), signal_row.get("entry_max"),
                 signal_row.get("stop_loss"), signal_row.get("tp1")))
            log.info(kv(event="mirror_intent", signal_id=sid,
                        symbol=signal_row["symbol"]))
            return True
        except Exception:
            self._gaps += 1
            log.exception(kv(event="mirror_intent_failed",
                             symbol=signal_row.get("symbol")))
            return False

    # ------------------------------------------------ adim 2: emir dongusu
    def _bars_since(self, symbol: str, ts: int | None) -> int:
        """Verilen andan bu yana arsivlenmis KAPANMIS 1h bar sayisi.
        Duvar saati degil bar sayisi: canli tracker ile ayni olcek
        (14 bar birebir karari)."""
        if not ts:
            return 0
        row = self._db.query_one(
            "SELECT COUNT(*) AS n FROM candles WHERE symbol=? "
            "AND interval='1h' AND ts>?", (symbol, ts))
        return int((row or {}).get("n") or 0)

    def sync_signals(self, signal_rows: list[dict]) -> int:
        """Acik (blocked=0) sinyalleri aynala: niyet + emir gonderimi.
        Istemci yoksa yalniz niyet kaydi kalir (adim 1 davranisi)."""
        if not self._enabled:
            return 0
        submitted = 0
        for row in signal_rows:
            self.record_intent(row)               # idempotent (dedup icinde)
            if self._client is None:
                continue                          # adim 1 davranisi: yalniz niyet
            m = self._db.query_one(
                "SELECT * FROM mirror_fills WHERE signal_id=?",
                (int(row["id"]),))
            if m is None or m["alpaca_status"] != "INTENT":
                continue
            try:
                is_long = row["direction"] == "LONG"
                # limit = KOTU uc (LONG entry_max / SHORT entry_min):
                # tracker'in worst-fill muhasebesiyle ayni taraf.
                limit = row["entry_max"] if is_long else row["entry_min"]
                risk = abs((limit or 0) - (row["stop_loss"] or 0))
                if not limit or risk <= 0:
                    continue
                qty = round(REF_RISK_USD / risk, 4)
                oid = self._client.submit_bracket(
                    row["symbol"], "buy" if is_long else "sell", qty,
                    limit, row["stop_loss"], row["tp1"])
                if oid:
                    self._db.execute(
                        "UPDATE mirror_fills SET alpaca_order_id=?, "
                        "alpaca_status='SUBMITTED', qty=?, entry_candle_ts=? "
                        "WHERE signal_id=?",
                        (str(oid), qty, row.get("entry_candle_ts"),
                         int(row["id"])))
                    submitted += 1
                    log.info(kv(event="mirror_submitted", order_id=oid,
                                symbol=row["symbol"], qty=qty))
            except Exception:
                self._gaps += 1
                log.exception(kv(event="mirror_submit_failed",
                                 symbol=row.get("symbol")))
        return submitted

    def poll(self) -> None:
        """Acik ayna kayitlarini broker durumuyla esitle + pencere/time-stop.
        Salt transkripsiyon: simulasyon yapilmaz, broker ne dediyse o."""
        if not self._enabled or self._client is None:
            return
        rows = self._db.query(
            "SELECT * FROM mirror_fills WHERE alpaca_status IN "
            "('SUBMITTED','FILLED')")
        for m in rows:
            try:
                self._poll_one(m)
            except Exception:
                self._gaps += 1
                log.exception(kv(event="mirror_poll_failed",
                                 symbol=m.get("symbol")))

    def _poll_one(self, m: dict) -> None:
        st = self._client.order_status(m["alpaca_order_id"]) or {}
        status = st.get("status")
        if status == "filled" and m["alpaca_status"] == "SUBMITTED":
            self._db.execute(
                "UPDATE mirror_fills SET alpaca_status='FILLED', "
                "alpaca_fill_price=?, alpaca_fill_ts=? WHERE id=?",
                (st.get("fill_price"), st.get("fill_ts"), m["id"]))
            return
        if status == "closed":
            self._db.execute(
                "UPDATE mirror_fills SET alpaca_status='CLOSED', "
                "alpaca_fill_price=COALESCE(?, alpaca_fill_price), "
                "alpaca_exit_price=?, alpaca_exit_ts=?, closed_reason=? "
                "WHERE id=?",
                (st.get("fill_price"), st.get("exit_price"),
                 st.get("exit_ts"), st.get("exit_reason"), m["id"]))
            return
        if status == "canceled":
            self._db.execute(
                "UPDATE mirror_fills SET alpaca_status='CANCELLED' "
                "WHERE id=?", (m["id"],))
            return
        # pencere: 14 kapanmis bar icinde dolum yoksa iptal (NOT_FILLED esi)
        if m["alpaca_status"] == "SUBMITTED" and self._bars_since(
                m["symbol"], m.get("entry_candle_ts")) >= self._fill_window:
            if self._client.cancel(m["alpaca_order_id"]):
                self._db.execute(
                    "UPDATE mirror_fills SET alpaca_status='CANCELLED', "
                    "closed_reason='WINDOW' WHERE id=?", (m["id"],))
            return
        # time-stop: dolumdan 28 kapanmis bar sonra pozisyonu kapat
        if m["alpaca_status"] == "FILLED" and self._bars_since(
                m["symbol"], m.get("alpaca_fill_ts")) >= self._max_track:
            res = self._client.close_position(m["symbol"], m.get("qty")) or {}
            self._db.execute(
                "UPDATE mirror_fills SET alpaca_status='CLOSED', "
                "alpaca_exit_price=?, alpaca_exit_ts=?, "
                "closed_reason='TIME' WHERE id=?",
                (res.get("price"), res.get("ts"), m["id"]))

    def diag(self) -> dict:
        """/diag icin ozet. Etiket sozlesme geregi sabittir (md. 4)."""
        n = self._db.query_one("SELECT COUNT(*) AS n FROM mirror_fills")
        by = {r["alpaca_status"]: r["n"] for r in self._db.query(
            "SELECT alpaca_status, COUNT(*) n FROM mirror_fills "
            "GROUP BY alpaca_status")}
        return {"label": "AYNA - karara girmez",
                "enabled": self._enabled,
                "client": self._client is not None,
                "intents": (n or {}).get("n", 0),
                "by_status": by,
                "gaps": self._gaps}
