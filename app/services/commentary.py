"""
CommentaryService - periyodik otomatik degerlendirme (bybit botundan uyarlama).

Claude'un elle yaptigi analiz kaliplarinin kural tabanli halidir: sonuclananlar,
basabas konumu, yon bilancosu, giris isabeti, orneklem uyarilari. LLM cagrisi
YOKTUR; deterministik sablonlardir ve dashboard'da boyle etiketlenir.

ABD uyarlamalari:
- pair -> symbol
- Rejim baglami eklenir (BULL/BEAR/NEUTRAL karsi-yon yorumu rejimle baglanir)
- Gap kaynakli derin kayip uyarisi (r < -1.3R => gece gap'i stop'u atlatti)
- EXPIRED (time-stop) orani yorumu: hedefe yurumeyen sinyal cokluğu tespiti

Uretim: seans icinde saatte bir (COMMENT_INTERVAL_SEC) + gun sonunda zorunlu.
Kayitlar DB'de tutulur (son 48), gist yedegine 0_commentary.json olarak yazilir.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from app.logging_setup import kv
from app.services.database import Database
from app.services.signal_tracker import SignalTracker

log = logging.getLogger("commentary")

_TABLE = """
CREATE TABLE IF NOT EXISTS commentary(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc TEXT NOT NULL,
  text TEXT NOT NULL,
  stats_json TEXT
);
"""

_DISCLAIMER = ("Tum sonuclar golge muhasebedir (varsayimsal giris, gap'e gore "
               "cikis, komisyon/spread yok); yatirim tavsiyesi degildir.")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fmt_r(v: float) -> str:
    return ("+" if v > 0 else "") + f"{v:.2f}R"


class CommentaryService:
    def __init__(self, db: Database, tracker: SignalTracker,
                 interval_sec: int = 3600) -> None:
        self._db = db
        self._tracker = tracker
        self._interval = interval_sec
        self._last = 0.0
        db.execute(_TABLE)

    # ------------------------------------------------------------ schedule
    def maybe_generate(self, regime: str = "") -> None:
        if time.time() - self._last >= self._interval:
            try:
                self.generate(regime)
            except Exception as exc:  # yorum motoru botu asla dusurmemeli
                log.error(kv(event="commentary_error", error=type(exc).__name__))
            self._last = time.time()

    # ------------------------------------------------------------ generate
    def generate(self, regime: str = "") -> dict:
        stats = self._tracker.stats()
        signals = self._tracker.recent_signals(500)
        prev = self._latest()
        prev_stats = (json.loads(prev["stats_json"])
                      if prev and prev.get("stats_json") else {})
        prev_ts = prev["ts_utc"] if prev else None

        text = self._compose(stats, signals, prev_stats, prev_ts, regime)
        row = {"ts_utc": _now_iso(), "text": text,
               "stats_json": json.dumps({
                   "decided": stats.get("decided_trades", 0),
                   "total_r": stats.get("total_r_multiple", 0.0),
                   "win_rate": stats.get("win_rate"),
               })}
        self._db.execute(
            "INSERT INTO commentary(ts_utc, text, stats_json) VALUES(?,?,?)",
            (row["ts_utc"], row["text"], row["stats_json"]))
        self._db.execute(
            "DELETE FROM commentary WHERE id NOT IN "
            "(SELECT id FROM commentary ORDER BY id DESC LIMIT 48)")
        log.info(kv(event="commentary_generated"))
        return row

    # -------------------------------------------------------------- compose
    def _compose(self, stats: dict, signals: list[dict], prev_stats: dict,
                 prev_ts: str | None, regime: str) -> str:
        p: list[str] = []
        decided = stats.get("decided_trades", 0)
        total_r = stats.get("total_r_multiple", 0.0) or 0.0
        cbo = stats.get("closed_by_outcome", {}) or {}
        w = cbo.get("WIN", {"count": 0, "sum_r": 0.0})
        losses = cbo.get("LOSS", {"count": 0, "sum_r": 0.0})
        expired = cbo.get("EXPIRED", {"count": 0, "sum_r": 0.0})

        # 1) Genel durum + onceki yoruma gore degisim
        if not decided:
            p.append("Henuz sonuclanan sinyal yok; motor kosul bekliyor. "
                     "Sert filtreli muhafazakar profilde bu normaldir.")
        else:
            wr = (stats.get("win_rate") or 0.0) * 100
            avg_win = (w["sum_r"] / w["count"]) if w["count"] else None
            be = (100 / (1 + avg_win)) if avg_win else None
            pos = ("basabasin uzerinde" if be is not None and wr > be else
                   "basabasin altinda" if be is not None else
                   "basabas icin kazanc ornegi bekleniyor")
            delta = ""
            if prev_stats:
                d_r = total_r - (prev_stats.get("total_r") or 0.0)
                d_n = decided - (prev_stats.get("decided") or 0)
                if d_n:
                    delta = (f" Onceki degerlendirmeden bu yana {d_n} sinyal "
                             f"sonuclandi, donem katkisi {_fmt_r(d_r)}.")
                else:
                    delta = " Onceki degerlendirmeden bu yana yeni sonuc yok."
            be_txt = f" (basabas ~%{be:.1f})" if be is not None else ""
            p.append(f"Toplam {decided} sonuclanan sinyal: {w['count']} WIN / "
                     f"{losses['count']} LOSS, isabet %{wr:.1f}{be_txt} -> "
                     f"{pos}. Kumulatif {_fmt_r(total_r)}.{delta}")

        # 2) Son pencerede sonuclananlar
        window = [s for s in signals
                  if s.get("closed_utc")
                  and s.get("outcome") in ("WIN", "LOSS")
                  and (prev_ts is None or s["closed_utc"] > prev_ts)]
        if window:
            det = ", ".join(
                f"{s['symbol']} {s['direction']} {s['outcome']} "
                f"{_fmt_r(s.get('r_multiple') or 0.0)}"
                for s in sorted(window, key=lambda x: x["closed_utc"])[:8])
            more = f" (+{len(window)-8} adet daha)" if len(window) > 8 else ""
            p.append(f"Bu donemde sonuclananlar: {det}{more}.")

        # 3) Gap kaynakli derin kayip uyarisi (ABD'ye ozgu)
        deep = [s for s in window
                if s["outcome"] == "LOSS" and (s.get("r_multiple") or 0) < -1.3]
        if deep:
            det = ", ".join(f"{s['symbol']} ({_fmt_r(s['r_multiple'])})"
                            for s in deep)
            p.append(f"Gap uyarisi: stop'un otesinde acilisla derin kayip - "
                     f"{det}. Gece gap riski bu piyasanin yapisal bedelidir; "
                     "bilanco filtresi disinda makro takvim gunleri de "
                     "izlenmeye deger.")

        # 4) Yon bilancosu + rejim baglamli yorum
        def side(direction: str):
            rows = [s for s in signals if s.get("direction") == direction
                    and s.get("outcome") in ("WIN", "LOSS")]
            r = sum(s.get("r_multiple") or 0.0 for s in rows)
            wn = sum(1 for s in rows if s["outcome"] == "WIN")
            return wn, len(rows) - wn, r

        lw, ll, lr = side("LONG")
        sw, sl, sr = side("SHORT")
        if (lw + ll) or (sw + sl):
            reg_txt = f" (guncel rejim: {regime})" if regime else ""
            p.append(f"Yon bilancosu -> LONG {lw}W/{ll}L ({_fmt_r(lr)}) | "
                     f"SHORT {sw}W/{sl}L ({_fmt_r(sr)}){reg_txt}.")
            if sr < -1 and lr > 1:
                p.append("Short tarafi bedel oduyor; ABD hisselerinin yapisal "
                         "yukari egilimi dusunulurse short esiklerinin daha da "
                         "sikilastirilmasi adayligi guclendi.")

        # 5) Time-stop (EXPIRED) orani
        if decided and expired["count"] >= max(3, decided // 3):
            p.append(f"Sinyallerin onemli kismi time-stop ile kapaniyor "
                     f"({expired['count']} adet, katki "
                     f"{_fmt_r(expired['sum_r'] or 0.0)}). Hedefe yurumeyen "
                     "setup cok -> tetik kalitesi / hedef mesafesi gozden "
                     "gecirilecek konular listesinde.")

        # 6) Giris isabeti
        filled = sum(1 for s in signals
                     if (s.get("outcome") or s.get("status"))
                     in ("WIN", "LOSS", "AMBIGUOUS", "EXPIRED", "FILLED"))
        nf = sum(1 for s in signals if s.get("outcome") == "NOT_FILLED")
        if filled + nf:
            fr = 100 * filled / (filled + nf)
            note = (" Dusuk isabet: giris bolgesine ~2 seans icinde gelinmiyor; "
                    "esik kalici olarak %40 altina inerse bolge genisligi "
                    "tartisilacak." if fr < 40 else "")
            p.append(f"Giris isabeti %{fr:.0f} ({filled} doldu / "
                     f"{nf} dolmadi).{note}")

        # 7) Acik pozisyonlar
        open_rows = [s for s in signals
                     if (s.get("outcome") or s.get("status"))
                     in ("PENDING", "FILLED")]
        if open_rows:
            oldest = min(open_rows, key=lambda s: s.get("created_utc") or "")
            p.append(f"Izlemede {len(open_rows)} acik sinyal; en eskisi "
                     f"{oldest['symbol']} ({oldest.get('created_utc', '')[:16]}"
                     " UTC).")

        # 8) Kapanis uyarilari
        if decided and decided < 30:
            p.append(f"Orneklem hala kucuk (n={decided}); 30-50 sonuclanmis "
                     "sinyalden once parametre karari verilmeyecek.")
        p.append(_DISCLAIMER)
        return "\n".join(p)

    # --------------------------------------------------------------- query
    def _latest(self) -> dict | None:
        rows = self._db.query(
            "SELECT ts_utc, text, stats_json FROM commentary "
            "ORDER BY id DESC LIMIT 1")
        return dict(rows[0]) if rows else None

    def latest(self) -> dict | None:
        row = self._latest()
        if row:
            row.pop("stats_json", None)
        return row

    def recent(self, limit: int = 5) -> list[dict]:
        rows = self._db.query(
            "SELECT ts_utc, text FROM commentary ORDER BY id DESC LIMIT ?",
            (limit,))
        return [dict(r) for r in rows]
