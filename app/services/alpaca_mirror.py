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

ADIM 1 kapsami: depo + niyet kaydi iskeleti. EMIR GONDERIMI YOK;
ALPACA_MIRROR_ENABLED varsayilan False. Adim 2: sahte istemciyle emir
dongusu. Adim 3: canli paper hesap + 2 hafta alarmsiz izleme (yanlis
alarm dersi). Adim 4: sapma esikleri OLCUMDEN ONCE yazilir, EOD
raporuna AYNA bolumu eklenir.
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


class AlpacaMirror:
    """Adim 1: yalniz niyet kaydi. Emir gonderimi adim 2'de gelir.

    db: services.database.Database (signals ile ayni dosya, AYRI tablo -
    ayrikligi tablo duzeyinde tutmak, gist yedeklemesinin aynayi da
    kapsamasini bedavaya getirir).
    """

    def __init__(self, db, enabled: bool = False, client=None) -> None:
        self._db = db
        self._enabled = bool(enabled)
        self._client = client          # adim 2: emir yetkili alpaca istemcisi
        self._gaps = 0                 # aynalanamayan sinyal sayaci (fail-open gorunurlugu)
        db.execute(_TABLE_SQL)
        db.execute(_INDEX_SQL)

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

    def diag(self) -> dict:
        """/diag icin ozet. Etiket sozlesme geregi sabittir (md. 4)."""
        n = self._db.query_one("SELECT COUNT(*) AS n FROM mirror_fills")
        return {"label": "AYNA - karara girmez",
                "enabled": self._enabled,
                "intents": (n or {}).get("n", 0),
                "gaps": self._gaps}
