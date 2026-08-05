"""
GistBackup - botun KENDI kayit tutma mekanizmasi. Insan mudahalesi gerektirmez.
Bybit reposundan tasindi; ABD uyarlamasi: evren buyuk (~300 sembol) oldugundan
mum arsivi default olarak yalnizca SINYAL URETEN sembollere yazilir
(GIST_CANDLE_MODE=signals). Dashboard bu gist'i degil canli API'yi okur;
gist, redeploy sonrasi self-healing + kalici istatistik arsividir.

Dongu:
1. STARTUP RESTORE: DB bos ise (redeploy/restart sonrasi ephemeral disk
   sifirlanmis) gist'ten mum arsivi + sinyal kayitlari geri yuklenir
   -> golge takip kaldigi yerden surer.
2. PERIYODIK SYNC: Her GIST_SYNC_INTERVAL_SEC'te (default 1 saat) guncel
   0_performance.json, 0_signals.json, 0_decisions.json, 0_meta.json ve
   candles_*.csv gist'e yazilir. Gist her yazimda revizyon tutar ->
   istatistik gecmisi otomatik arsivlenir.

Gist, MARKER aciklamasiyla otomatik bulunur/olusturulur; GIST_ID env ile
sabitlemek istege baglidir. Sync hatalari sadece loglanir - taramayi durdurmaz.
"""
from __future__ import annotations

import io
import json
import logging
import time
from datetime import datetime, timezone

from app.integrations.gist_client import GistClient
from app.logging_setup import kv
from app.services.signal_tracker import SignalTracker

log = logging.getLogger("gist_backup")

MARKER = "midas-signal-bot-data (auto-managed, do not rename)"
_INTERVALS = ["1h", "1d"]


def _candles_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    buf.write("ts,open,high,low,close,volume\n")
    for r in rows:
        buf.write(f"{r['ts']},{r['open']},{r['high']},{r['low']},"
                  f"{r['close']},{r['volume']}\n")
    return buf.getvalue()


def _parse_candles_csv(text: str) -> list[tuple]:
    rows: list[tuple] = []
    for line in text.strip().splitlines()[1:]:
        parts = line.split(",")
        if len(parts) == 6:
            try:
                rows.append((int(parts[0]), float(parts[1]), float(parts[2]),
                             float(parts[3]), float(parts[4]), float(parts[5])))
            except ValueError:
                continue
    return rows


class GistBackup:
    def __init__(self, client: GistClient, tracker: SignalTracker,
                 sync_interval_sec: int = 3600, pinned_gist_id: str = "",
                 candle_mode: str = "signals", candle_max_rows: int = 3000,
                 meta_provider=None, commentary_provider=None,
                 candle_retention_days: int = 30) -> None:
        self._client = client
        self._tracker = tracker
        self._meta = meta_provider or (lambda: {})   # rejim/evren/izleme listesi
        self._commentary = commentary_provider       # None -> yorum dosyasi yazilmaz
        self._candle_mode = candle_mode              # signals | all | off
        self._candle_max_rows = candle_max_rows
        self._retention_days = candle_retention_days
        self._interval = sync_interval_sec
        self._gist_id: str | None = pinned_gist_id or None
        self._last_sync: float = 0.0
        # v4.10: zaman damgasi SURECLE BIRLIKTE OLMESIN. Eskiden yalniz
        # bellekteydi; her restart'ta None oluyordu ve "yedek ne zaman
        # alindi" sorusu CEVAPSIZ kaliyordu (oz-denetim de bunu korluk
        # sayip bildirdi). Artik meta tablosunda kalici.
        self._last_sync_utc: str | None = self._read_meta_sync()

    # -------------------------------------------------- kalici zaman damgasi
    _META_KEY = "gist_last_sync_utc"

    def _read_meta_sync(self) -> str | None:
        try:
            row = self._tracker._db.query_one(
                "SELECT value FROM meta WHERE key=?", (self._META_KEY,))
            return row["value"] if row else None
        except Exception:
            return None

    def _write_meta_sync(self, iso: str) -> None:
        try:
            self._tracker._db.execute(
                "INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)",
                (self._META_KEY, iso))
        except Exception:
            log.exception(kv(event="gist_meta_write_failed"))

    # ------------------------------------------------------------- durum
    def info(self) -> dict:
        return {
            "gist_id": self._gist_id,
            "gist_url": (self._client.gist_url(self._gist_id)
                         if self._gist_id else None),
            "last_sync_utc": self._last_sync_utc,
            "age_hours": self._age_hours(),
            "sync_interval_sec": self._interval,
            "candle_mode": self._candle_mode,
        }

    def _age_hours(self) -> float | None:
        """Son basarili yedegin yasi (saat). Restart'tan bagimsiz."""
        if not self._last_sync_utc:
            return None
        try:
            t = datetime.strptime(self._last_sync_utc[:19],
                                  "%Y-%m-%dT%H:%M:%S").replace(
                tzinfo=timezone.utc)
            return round((datetime.now(timezone.utc) - t).total_seconds()
                         / 3600, 2)
        except Exception:
            return None

    # ------------------------------------------------------------- sync
    def build_files(self) -> dict[str, str]:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        # "0_" oneki: istatistik dosyalari alfabetik olarak mum CSV'lerinden ONCE
        # gelsin diye (GitHub Gist API icerik butcesini alfabetik sirayla harcar).
        files = {
            "0_performance.json": json.dumps(self._tracker.stats(), indent=2),
            "0_signals.json": json.dumps(self._tracker.recent_signals(500), indent=2),
            "0_decisions.json": json.dumps(self._tracker.recent_decisions(2000), indent=2),
            "0_meta.json": json.dumps({"synced_utc": now, **self._meta()}, indent=2),
            "README.md": (f"# midas-signal-bot data\nAuto-synced: {now}\n\n"
                          "Shadow-tracking stats and backtest dataset for US stocks "
                          "listed on Midas. Managed by the bot - do not edit manually.\n"),
        }
        if self._commentary is not None:
            try:
                files["0_commentary.json"] = json.dumps(
                    self._commentary(), indent=2)
            except Exception:
                log.exception(kv(event="gist_commentary_error"))
        if self._candle_mode == "off":
            return files
        symbols = self._tracker.archive_symbols(self._retention_days)
        for symbol in symbols:
            for interval in _INTERVALS:
                rows = self._tracker.export_candles(symbol, interval)
                if rows:
                    files[f"candles_{symbol}_{interval}.csv"] = _candles_csv(
                        rows[-self._candle_max_rows:])
        return files

    def sync(self) -> bool:
        files = self.build_files()
        if self._gist_id is None:
            self._gist_id = self._client.find_gist(MARKER)
        if self._gist_id is None:
            self._gist_id = self._client.create_gist(MARKER, files)
            ok = self._gist_id is not None
        else:
            payload: dict = dict(files)
            try:
                existing = self._client.fetch_gist(self._gist_id) or {}
                stale = [n for n in existing
                         if n.startswith("candles_") and n not in files]
                for name in stale:
                    payload[name] = None          # saklama disi -> gist'ten sil
                if stale:
                    log.info(kv(event="gist_prune", removed=len(stale)))
            except Exception:
                log.exception(kv(event="gist_prune_error"))
            ok = self._client.update_gist(self._gist_id, payload)
        if ok:
            self._last_sync = time.time()
            self._last_sync_utc = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ")
            self._write_meta_sync(self._last_sync_utc)
            log.info(kv(event="gist_sync_ok", gist_id=self._gist_id,
                        files=len(files)))
        return ok

    def maybe_sync(self) -> None:
        """Scheduler dongusunden cagrilir; araligi dolmadiysa hicbir sey yapmaz."""
        if time.time() - self._last_sync >= self._interval:
            try:
                self.sync()
            except Exception:
                log.exception(kv(event="gist_sync_error"))

    def heartbeat(self, payload: dict) -> bool:
        """Hafif nabiz: tek dosyalik guncelleme (0_heartbeat.json).
        Uzaktan izleme icin onbellege takilmayan taze telemetri kanali;
        tam sync'ten bagimsiz, 15 dk'da bir cagrilir (1 API cagrisi)."""
        if self._gist_id is None:
            self._gist_id = self._client.find_gist(MARKER)
        if self._gist_id is None:
            return False   # gist ilk tam sync'te olusur; nabiz o zamana kadar bekler
        return self._client.update_gist(
            self._gist_id, {"0_heartbeat.json": json.dumps(payload, indent=2)})

    def fetch_meta(self) -> dict | None:
        """Gist'teki 0_meta.json icerigi (evren tohumlama icin)."""
        if self._gist_id is None:
            self._gist_id = self._client.find_gist(MARKER)
        if self._gist_id is None:
            return None
        files = self._client.fetch_gist(self._gist_id)
        if not files or "0_meta.json" not in files:
            return None
        try:
            return json.loads(files["0_meta.json"])
        except (json.JSONDecodeError, TypeError):
            return None

    # ----------------------------------------------------------- restore
    def restore_if_empty(self) -> bool:
        """DB bos ise gist'ten geri yukle (redeploy sonrasi self-healing)."""
        if self._tracker.candles_count() > 0:
            return False  # veri zaten var, restore gerekmez
        if self._gist_id is None:
            self._gist_id = self._client.find_gist(MARKER)
        if self._gist_id is None:
            log.info(kv(event="gist_restore_skip", reason="no existing gist"))
            return False
        files = self._client.fetch_gist(self._gist_id)
        if not files:
            return False

        candles_total = 0
        for name, content in files.items():
            if name.startswith("candles_") and name.endswith(".csv"):
                core = name[len("candles_"):-len(".csv")]
                symbol, _, interval = core.rpartition("_")
                if symbol and interval:
                    candles_total += self._tracker.import_candles(
                        symbol, interval, _parse_candles_csv(content))
        signals_total = 0
        sig_file = files.get("0_signals.json")
        if sig_file:
            try:
                signals_total = self._tracker.import_signals(json.loads(sig_file))
            except (json.JSONDecodeError, TypeError):
                log.warning(kv(event="gist_restore_signals_parse_error"))
        log.info(kv(event="gist_restore_ok", gist_id=self._gist_id,
                    candles=candles_total, signals=signals_total))
        return True
