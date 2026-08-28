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


# ---- Hipotez 7 (28 Agu kapisi): sonuc siniflari ------------------------
# Iki defterin sozlugu farkli; kiyas icin ORTAK sinifa cevrilir.
# Siniflar sonuc gorulmeden sabitlendi (28 Agu 14:00 UTC).
DOLMADI, KAZANC, ZARAR, SURE, BELIRSIZ = ("DOLMADI", "KAZANC", "ZARAR",
                                          "SURE", "BELIRSIZ")


def ledger_class(status: str | None, outcome: str | None,
                 fill_price: float | None) -> str | None:
    """Golge defter sonucu -> ortak sinif. Sonuclanmamis kayit None."""
    if outcome == "NOT_FILLED":
        return DOLMADI
    if outcome == "WIN":
        return KAZANC
    if outcome == "LOSS":
        return ZARAR
    if outcome == "EXPIRED":
        return SURE
    if outcome == "AMBIGUOUS":
        return BELIRSIZ
    return None                      # PENDING/FILLED: henuz sonuc yok


def mirror_class(alpaca_status: str | None,
                 closed_reason: str | None) -> str | None:
    """Ayna sonucu -> ortak sinif. Hala acik pozisyon (FILLED) None."""
    if alpaca_status == "CANCELLED":
        return DOLMADI               # WINDOW ya da broker iptali
    if alpaca_status == "CLOSED":
        if closed_reason == "TP":
            return KAZANC
        if closed_reason == "STOP":
            return ZARAR
        if closed_reason == "TIME":
            return SURE
        return BELIRSIZ              # bilinmeyen kapanis nedeni gizlenmez
    return None                      # INTENT/SUBMITTED/FILLED: sonuc yok


def disagreement_report(rows: list[dict]) -> dict:
    """Eslesmis ciftlerin sonuc uyusmazligi (hipotez 7). Saf fonksiyon:
    veritabanina degil, satir listesine bakar - hem servis hem
    tools/mirror_disagreement.py ayni hesabi kullansin diye."""
    karsilastirilan, uyusmaz, ornekler = 0, 0, []
    yalniz_defter_girdi = yalniz_ayna_girdi = 0
    defter_kazanc = ayna_kazanc = 0
    bekleyen = 0
    for r in rows:
        d = ledger_class(r.get("status"), r.get("outcome"),
                         r.get("fill_price"))
        a = mirror_class(r.get("alpaca_status"), r.get("closed_reason"))
        if d is None or a is None:
            bekleyen += 1            # "henuz bilmiyoruz" - paydaya girmez
            continue
        karsilastirilan += 1
        if d == KAZANC:
            defter_kazanc += 1
        if a == KAZANC:
            ayna_kazanc += 1
        if d == a:
            continue
        uyusmaz += 1
        if d == DOLMADI and a != DOLMADI:
            yalniz_ayna_girdi += 1
        elif a == DOLMADI and d != DOLMADI:
            yalniz_defter_girdi += 1
        if len(ornekler) < 12:
            ornekler.append({"symbol": r.get("symbol"),
                             "defter": d, "ayna": a})
    oran = round(uyusmaz / karsilastirilan, 3) if karsilastirilan else None
    return {"label": "AYNA - karara girmez",
            "karsilastirilan": karsilastirilan,
            "sonuclanmamis": bekleyen,
            "uyusmaz": uyusmaz,
            "uyusmazlik_orani": oran,
            "esik": 0.25,
            "esik_asildi": (oran is not None and oran >= 0.25),
            "yon": {"yalniz_defter_girdi": yalniz_defter_girdi,
                    "yalniz_ayna_girdi": yalniz_ayna_girdi,
                    "defter_kazanc": defter_kazanc,
                    "ayna_kazanc": ayna_kazanc},
            "ornekler": ornekler}


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
            # v4.33 (14 Agu DE/JNJ gozlemi): dolum penceresi COKTAN gecmis
            # sinyale emir GONDERILMEZ - ayna hayata ortadan katildiysa bu
            # bir olcum cifti degil kurulus artefaktidir; emir zaten bir
            # sonraki tick'te WINDOW iptali yerdi ve metrigi kirletirdi.
            # LATE_ONBOARD kaydi metrics()'ten DISLANIR.
            if self._bars_since(row["symbol"],
                                row.get("entry_candle_ts")) >= self._fill_window:
                self._db.execute(
                    "UPDATE mirror_fills SET alpaca_status='CANCELLED', "
                    "closed_reason='LATE_ONBOARD' WHERE signal_id=?",
                    (int(row["id"]),))
                log.info(kv(event="mirror_late_onboard",
                            symbol=row["symbol"]))
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

    def metrics(self) -> dict:
        """HAM FARK olcumleri (v4.33) - sapma esikleri on-kaydinin
        (config-lock v4.32-C, Serhat onayi 13 Agu) gosterge yarisi.

        ESLESMIS CIFT tanimi: ayna emri sinyalin DOGUMUNDA gonderilmis
        (LATE_ONBOARD haric) VE iki taraf da dolum sorusunu karara
        baglamis. Ham degerler her zaman raporlanir; kademe yalniz
        ISARETTIR - hicbir esik/parametre otomatik degismez.
          kademe 0: fark izleme sinirlarinin altinda
          kademe 1 (izleme notu, eylemsiz): |oran farki|>=0.10 veya
                    |ort. fiyat farki|>=0.08R
          kademe 2 (karar tetigi): >=20 cift VE >=14 gun VE
                    (|oran farki|>=0.20 veya |ort. fiyat farki|>=0.15R)
                    -> karar toplantisi acilir (config-lock sureci)."""
        rows = self._db.query(
            "SELECT m.alpaca_status, m.alpaca_fill_price, m.created_utc, "
            "s.fill_price, s.stop_loss, s.status, s.outcome, s.direction, "
            "s.entry_min, s.entry_max "
            "FROM mirror_fills m JOIN signals s ON s.id=m.signal_id "
            "WHERE COALESCE(m.closed_reason,'') != 'LATE_ONBOARD'")
        pairs = []
        for r in rows:
            mirror_decided = r["alpaca_status"] in ("FILLED", "CLOSED",
                                                    "CANCELLED")
            ledger_filled = r["fill_price"] is not None
            ledger_decided = ledger_filled or (
                r["status"] == "CLOSED" and r["outcome"] == "NOT_FILLED")
            if mirror_decided and ledger_decided:
                pairs.append(r)
        n = len(pairs)
        out = {"matched": n, "ledger_fill_rate": None,
               "mirror_fill_rate": None, "fill_rate_diff": None,
               "avg_price_adv_r": None, "price_pairs": 0, "tier": 0,
               "since_utc": min((r["created_utc"] for r in pairs),
                                default=None)}
        if n == 0:
            return out
        lf = sum(1 for r in pairs if r["fill_price"] is not None) / n
        mf = sum(1 for r in pairs
                 if r["alpaca_status"] in ("FILLED", "CLOSED")) / n
        out["ledger_fill_rate"] = round(lf, 3)
        out["mirror_fill_rate"] = round(mf, 3)
        out["fill_rate_diff"] = round(mf - lf, 3)
        advs = []
        for r in pairs:
            if r["fill_price"] is None or r["alpaca_fill_price"] is None:
                continue
            # v4.42 (20 Agu CIEN vakasi): payda DOLUM riski degil TASARIM
            # riski (bolgenin kotu ucu <-> stop). Gap'te bolge ALTINDAN
            # dolan islemde dolum riski cokuyor ve tek cift ortalamayi
            # patlatiyordu (CIEN: -10.5R "avantaj" - 13 ciftin toplam
            # sapmasinin %64'u tek basina; cikarilinca ortalama isaret
            # degistiriyordu). Tasarim riski sinyal basina SABIT payda.
            is_long = r["direction"] == "LONG"
            ref = r["entry_max"] if is_long else r["entry_min"]
            risk = abs((ref or 0) - (r["stop_loss"] or 0))
            if risk <= 0:
                continue
            # pozitif = ayna DAHA IYI fiyat aldi (LONG'da daha ucuz,
            # SHORT'ta daha pahali satti) -> defter fazla kotumser yonu
            sign = 1 if is_long else -1
            advs.append(sign * (r["fill_price"] - r["alpaca_fill_price"])
                        / risk)
        if advs:
            out["price_pairs"] = len(advs)
            out["avg_price_adv_r"] = round(sum(advs) / len(advs), 3)
        rate_d = abs(out["fill_rate_diff"] or 0)
        price_d = abs(out["avg_price_adv_r"] or 0)
        days = 0.0
        if out["since_utc"]:
            try:
                t0 = datetime.strptime(out["since_utc"],
                                       "%Y-%m-%dT%H:%M:%SZ")
                days = (datetime.now(timezone.utc)
                        - t0.replace(tzinfo=timezone.utc)).days
            except ValueError:
                pass
        if n >= 20 and days >= 14 and (rate_d >= 0.20 or price_d >= 0.15):
            out["tier"] = 2
        elif rate_d >= 0.10 or price_d >= 0.08:
            out["tier"] = 1
        return out

    def disagreement(self) -> dict:
        """HIPOTEZ 7 OLCUSU (28 Agu kapisi): golge defter ile ayna AYNI
        sonuca mi vardi? SALT OLCUM - hicbir esigi degistirmez (md. 5).

        On-kayit (research-log hipotez 7, 17 Agu): "golge/ayna sonuc
        UYUSMAZLIGI orani ve yonu raporlanir; uyusmazlik >= %25 ise
        dolum modeli karar toplantisina tasinir."

        OKUMA YORUMU - kapi gunu sayilar GORULMEDEN sabitlendi
        (28 Agu 14:00 UTC, veri henuz cekilmedi):
        - Payda: eslesmis ciftlerden IKI TARAFI DA sonuclanmis olanlar.
          Ayna tarafi hala acik (FILLED) olan cift sayilmaz - "henuz
          bilmiyoruz" ile "ayrildilar" ayni sey degildir (2.2 refleksi).
        - Uyusmazlik: sonuc SINIFLARI farkli. 'Dolmadi' bir siniftir,
          yani "biri girdi digeri girmedi" de uyusmazliktir - hipotez
          7'nin dogdugu FTNT vakasi tam olarak buydu.
        - Yon: hangi taraf daha sik girdi / daha sik kazandi.
        Bu yorum simdiden yazildi ki sonuc gelince "hangi paydayla
        %25'in altinda kalir" oynamasi yapilamasin.
        """
        rows = self._db.query(
            "SELECT m.alpaca_status, m.closed_reason, s.outcome, s.status, "
            "s.fill_price, s.symbol "
            "FROM mirror_fills m JOIN signals s ON s.id=m.signal_id "
            "WHERE COALESCE(m.closed_reason,'') != 'LATE_ONBOARD'")
        return disagreement_report(rows)

    def diag(self) -> dict:
        """/diag icin ozet. Etiket sozlesme geregi sabittir (md. 4)."""
        n = self._db.query_one("SELECT COUNT(*) AS n FROM mirror_fills")
        by = {r["alpaca_status"]: r["n"] for r in self._db.query(
            "SELECT alpaca_status, COUNT(*) n FROM mirror_fills "
            "GROUP BY alpaca_status")}
        out = {"label": "AYNA - karara girmez",
               "enabled": self._enabled,
               "client": self._client is not None,
               "intents": (n or {}).get("n", 0),
               "by_status": by,
               "gaps": self._gaps}
        try:
            out["metrics"] = self.metrics()
        except Exception:
            log.exception(kv(event="mirror_metrics_error"))
        try:
            out["disagreement"] = self.disagreement()   # hipotez 7 (28 Agu)
        except Exception:
            log.exception(kv(event="mirror_disagreement_error"))
        return out
