"""
TEMA RADARI (v4.54, 27 Eki 2026 - Serhat istegi).

Ne yapar: tema ETF'lerinin (uranyum, sebeke, robotik, savunma, uzay,
kuantum ...) SPY'a gore GORELI GUCUNU olcer, siralar ve "para bu temaya
akiyor" isaretini Telegram'a yollar. Amac bir sonraki tema dalgasini
haberden ONCE fark etmek: goreli guc cogu zaman haberden once doner.

SALT OLCUM - KARARA KARISMAZ (anayasa 2.4):
- signal_engine / strategies/* / signal_tracker bu modulu import ETMEZ
  (tests/test_theme_radar.py AST duzeyinde kilitler).
- Izleme listesine, golge deftere, kohorta, go-live sayacina dokunmaz.
- Telegram mesaji ISLEM SINYALI DEGILDIR; kendi bayragiyla gider
  (THEME_RADAR_TELEGRAM) ve golge modun TELEGRAM_ENABLED=false kararini
  delmez (o bayrak motorun islem sinyalleri icindir).

Veri davranisi (anayasa 2.1 / 2.2 - uydurma yok, sessiz kapanma yok):
- SPY yoksa / bayatsa: siralama URETILMEZ (durum no_benchmark / stale),
  ISINIYOR/SOGUYOR isareti yok, kesinti basina TEK uyari mesaji
  (alarm gurultusu alarmi oldurur - anayasa 6).
- Tek ETF eksik / kisa gecmisli / bayat / gun eksikli: o satir "veri yok"
  listesine nedeniyle gider, siralamaya girmez. Doldurma/tahmin yok.
- Gecerli ETF sayisi evrenin yarisindan (en az 5) azsa: insufficient,
  isaret yok (5 ETF icinde "ilk 3" anlamsizdir).
- Bir "sicak" temanin verisi o gun gelmezse SOGUYOR hukmu VERILMEZ;
  sicak kalir (veri yok != soguma).

ON-KAYITLI KURALLAR (sonuca bakilarak degistirilmez; degisiklik tarihli
not + Serhat onayi ister - config-lock.md 2026-10-27 kaydi):
- RS(n) = ETF n-gun getirisi - SPY n-gun getirisi (yuzde puan)
- Bilesik RS = 0.5 x RS(20g) + 0.3 x RS(60g) + 0.2 x RS(120g)
- ISINIYOR: siralamada ilk TOP_N  VE  RS cizgisi (ETF/SPY) son 60 gunun
  zirvesinde  VE  kapanis SMA50 ustunde  VE  hacim(10g ort)/hacim(50g ort)
  >= VOL_MIN  VE  tema zaten sicak degil  VE  son COOLDOWN gunde
  ISINIYOR almamis (testere/whipsaw freni).
- SOGUYOR: sicak tema SMA50 altinda kapatti -> bir kez bildirilir,
  sicak listesinden cikar.
- HAFTALIK: ISO haftasinin ilk basarili kosumunda tam siralama
  (+ gecen haftaya gore siralama degisimi).

Saf hesap fonksiyonlari I/O yapmaz; ThemeRadar yalniz meta tablosuna
durum yazar (restart'ta tekrar bildirim olmasin - anayasa 6 "turetilmis
veriyi bellekte tutmak" dersi).
"""
from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, timezone

from app.logging_setup import kv

log = logging.getLogger("theme_radar")

BENCH = "SPY"
LOOKBACKS = (20, 60, 120)          # ~4 hafta, ~12 hafta, ~6 ay (islem gunu)
WEIGHTS = (0.5, 0.3, 0.2)
RS_HIGH_WINDOW = 60                # RS cizgisi zirvesi penceresi
MA_LEN = 50
VOL_SHORT, VOL_LONG = 10, 50
MIN_BARS = max(LOOKBACKS) + 1      # 121 hizali bar
MAX_GAP_DAYS = 2                   # son MIN_BARS SPY gununde izin verilen eksik


@dataclass(frozen=True)
class RadarParams:
    top_n: int = 3
    vol_ratio_min: float = 1.2
    cooldown_days: int = 14
    max_bar_age_days: int = 5      # SPY son bari bundan eskiyse bayat


def parse_universe(spec: str) -> list[tuple[str, str]]:
    """'URA:Uranyum,GRID:Sebeke' -> [('URA','Uranyum'), ('GRID','Sebeke')].
    SPY (kiyas) ve tekrarlar atlanir; etiketsiz sembolde etiket = sembol."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for part in (spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        sym, _, label = part.partition(":")
        sym = sym.strip().upper()
        if not sym or sym == BENCH or sym in seen:
            continue
        seen.add(sym)
        out.append((sym, label.strip() or sym))
    return out


def _bar_date(ts_ms: int) -> date:
    # yfinance gunluk index'i ET gece yarisi (UTC 04/05:00) ya da naive
    # tarih (UTC 00:00) gelir; ikisi de UTC'de AYNI takvim gunune duser.
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).date()


def _series_map(series) -> dict[date, tuple[float, float]]:
    return {_bar_date(c.ts): (float(c.close), float(c.volume))
            for c in series.candles}


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _metrics(sym: str, label: str, closes: list[float],
             bench: list[float], vols: list[float]) -> dict | None:
    """Hizali seriler (eski -> yeni) uzerinden tek satir. Gecersiz fiyatta
    None (hesaplanamadi) - sifira bolme/negatif fiyatla sayi uretilmez."""
    if min(closes) <= 0 or min(bench) <= 0:
        return None
    rs = {}
    for n in LOOKBACKS:
        r_etf = closes[-1] / closes[-1 - n] - 1
        r_spy = bench[-1] / bench[-1 - n] - 1
        rs[n] = round((r_etf - r_spy) * 100, 2)
    composite = round(sum(w * rs[n] for w, n in zip(WEIGHTS, LOOKBACKS)), 2)
    ratio = [c / b for c, b in zip(closes, bench)]
    window = ratio[-RS_HIGH_WINDOW:]
    rs_line_high = ratio[-1] >= max(window) * (1 - 1e-9)
    ma50 = _mean(closes[-MA_LEN:])
    vol_long = _mean(vols[-VOL_LONG:])
    vol_short = _mean(vols[-VOL_SHORT:])
    # hacim verisi yoksa (0) oran URETILMEZ -> ISINIYOR sarti gecemez
    vol_ratio = round(vol_short / vol_long, 2) if vol_long > 0 else None
    return {
        "symbol": sym, "label": label,
        "close": round(closes[-1], 4),
        "rs20": rs[20], "rs60": rs[60], "rs120": rs[120],
        "composite": composite,
        "rs_line_high": bool(rs_line_high),
        "above_ma50": closes[-1] > ma50,
        "ma50_dist_pct": round((closes[-1] / ma50 - 1) * 100, 2),
        "vol_ratio": vol_ratio,
    }


def min_valid(universe_size: int) -> int:
    return max(5, math.ceil(universe_size / 2))


def compute_report(daily: dict, universe: list[tuple[str, str]],
                   today: date, params: RadarParams = RadarParams()) -> dict:
    """daily: {sembol: KlineSeries} (kapanmis gunluk barlar, SPY dahil)."""
    report = {
        "computed_for": today.isoformat(), "asof": None, "status": None,
        "rows": [], "missing": [], "universe_size": len(universe),
        "min_valid": min_valid(len(universe)),
        "rule": {"weights": list(WEIGHTS), "lookbacks": list(LOOKBACKS),
                 "rs_high_window": RS_HIGH_WINDOW, "ma": MA_LEN,
                 "top_n": params.top_n, "vol_ratio_min": params.vol_ratio_min,
                 "cooldown_days": params.cooldown_days},
    }
    spy = daily.get(BENCH)
    if spy is None or len(spy) < MIN_BARS:
        report["status"] = "no_benchmark"
        return report
    spy_map = _series_map(spy)
    spy_dates = sorted(spy_map)
    asof = spy_dates[-1]
    report["asof"] = asof.isoformat()
    if (today - asof).days > params.max_bar_age_days:
        report["status"] = "stale"
        return report

    recent = spy_dates[-MIN_BARS:]
    rows, missing = [], []
    for sym, label in universe:
        series = daily.get(sym)
        if series is None or not len(series):
            missing.append({"symbol": sym, "label": label, "reason": "veri yok"})
            continue
        m = _series_map(series)
        last = max(m)
        if last != asof:
            # ETF'in son bari SPY'inkiyle ayni gun degil: bayat seriyi
            # bugunun degeri gibi siralamak 2.1 ihlali olurdu
            missing.append({"symbol": sym, "label": label,
                            "reason": f"bayat (son bar {last.isoformat()})"})
            continue
        gaps = sum(1 for d in recent if d not in m)
        if gaps > MAX_GAP_DAYS:
            missing.append({"symbol": sym, "label": label,
                            "reason": f"eksik gun ({gaps})"})
            continue
        dates = [d for d in spy_dates if d in m]
        if len(dates) < MIN_BARS:
            missing.append({"symbol": sym, "label": label,
                            "reason": f"kisa gecmis ({len(dates)} bar)"})
            continue
        row = _metrics(sym, label,
                       [m[d][0] for d in dates],
                       [spy_map[d][0] for d in dates],
                       [m[d][1] for d in dates])
        if row is None:
            missing.append({"symbol": sym, "label": label,
                            "reason": "hesaplanamadi (gecersiz fiyat)"})
            continue
        rows.append(row)

    rows.sort(key=lambda r: r["composite"], reverse=True)
    for i, r in enumerate(rows, start=1):
        r["rank"] = i
    report["rows"] = rows
    report["missing"] = missing
    report["status"] = ("ok" if len(rows) >= report["min_valid"]
                        else "insufficient")
    return report


def evaluate_signals(report: dict, state: dict, params: RadarParams,
                     today: date) -> tuple[list[dict], dict]:
    """ISINIYOR / SOGUYOR olaylari + guncel durum (girdi durumu DEGISMEZ).
    Durum 'ok' degilse hicbir isaret uretilmez (fail-closed)."""
    st = json.loads(json.dumps(state or {}))
    hot: dict = st.setdefault("hot", {})
    last: dict = st.setdefault("last_alert", {})
    events: list[dict] = []
    if report.get("status") != "ok":
        return events, st
    by_sym = {r["symbol"]: r for r in report["rows"]}

    for sym in sorted(hot):
        row = by_sym.get(sym)
        if row is None:
            continue            # veri yok != soguma; hukum verilmez
        if not row["above_ma50"]:
            events.append({"type": "cooling", "row": row, "since": hot[sym]})
            del hot[sym]

    for row in report["rows"]:
        sym = row["symbol"]
        if sym in hot or row["rank"] > params.top_n:
            continue
        if not (row["rs_line_high"] and row["above_ma50"]):
            continue
        if row["vol_ratio"] is None or row["vol_ratio"] < params.vol_ratio_min:
            continue
        prev = last.get(sym)
        if prev and (today - date.fromisoformat(prev)).days < params.cooldown_days:
            continue
        events.append({"type": "heating", "row": row})
        hot[sym] = today.isoformat()
        last[sym] = today.isoformat()
    return events, st


# ---------------------------------------------------------------- metinler
# Bot mesajlariyla ayni gelenek: duz metin, ASCII (parse_mode yok).
_FOOTER = ("Not: islem sinyali DEGIL - tema bilgisi. Motor, izleme listesi "
           "ve golge defter etkilenmez.")


def _pp(v: float | None) -> str:
    return f"{v:+.1f}pp" if v is not None else "-"


def render_heating(row: dict, report: dict) -> str:
    n = len(report["rows"])
    return "\n".join([
        f"TEMA RADARI | ISINAN TEMA: {row['label']} ({row['symbol']})",
        f"Siralama: {row['rank']}/{n} | bilesik RS {_pp(row['composite'])} "
        f"(SPY'a gore)",
        f"RS 4 hafta {_pp(row['rs20'])} | 12 hafta {_pp(row['rs60'])} | "
        f"6 ay {_pp(row['rs120'])}",
        f"RS cizgisi {RS_HIGH_WINDOW} gunun zirvesinde | fiyat 50G "
        f"ortalamanin %{row['ma50_dist_pct']:+.1f} ustunde",
        f"Hacim: son 10 gun ort. = 50 gun ort. x{row['vol_ratio']:.2f} "
        f"(para girisi isareti)",
        f"Veri: {report['asof']} kapanisi",
        _FOOTER,
    ])


def render_cooling(row: dict, since: str, report: dict) -> str:
    n = len(report["rows"])
    return "\n".join([
        f"TEMA RADARI | SOGUYAN TEMA: {row['label']} ({row['symbol']})",
        f"Kapanis 50G ortalamanin altina indi (%{row['ma50_dist_pct']:+.1f}). "
        f"Sicak isareti {since} tarihinden beri aktifti.",
        f"Siralama: {row['rank']}/{n} | bilesik RS {_pp(row['composite'])}",
        f"Veri: {report['asof']} kapanisi",
        _FOOTER,
    ])


def _rank_delta(sym: str, rank: int, prev: dict) -> str:
    if not prev:
        return ""
    p = prev.get(sym)
    if p is None:
        return " (yeni)"
    d = p - rank
    return " (=)" if d == 0 else f" ({d:+d})"


def render_weekly(report: dict, prev_ranks: dict, hot: dict) -> str:
    lines = [
        "TEMA RADARI - HAFTALIK SIRALAMA",
        f"Veri: {report['asof']} kapanisi | SPY'a gore goreli guc (yuzde puan)",
        "Bilesik = 0.5 x 4 hafta + 0.3 x 12 hafta + 0.2 x 6 ay",
        "",
    ]
    for r in report["rows"]:
        marks = []
        if r["rs_line_high"]:
            marks.append("Z")
        if r["above_ma50"]:
            marks.append("M")
        if r["symbol"] in hot:
            marks.append("*")
        tag = f" [{' '.join(marks)}]" if marks else ""
        lines.append(f"{r['rank']:>2}. {r['symbol']} {r['label']} "
                     f"{_pp(r['composite'])}"
                     f"{_rank_delta(r['symbol'], r['rank'], prev_ranks)}{tag}")
    lines += ["",
              "Z = RS cizgisi 60g zirvede | M = 50G ort. ustunde | * = sicak tema"]
    if hot:
        lines.append("Sicak temalar: " + ", ".join(
            f"{s} ({d}'den beri)" for s, d in sorted(hot.items())))
    else:
        lines.append("Sicak tema yok.")
    if report["missing"]:
        lines.append("Veri yok: " + ", ".join(
            f"{m['symbol']} ({m['reason']})" for m in report["missing"]))
    lines.append(_FOOTER)
    return "\n".join(lines)


def render_outage(report: dict) -> str:
    st = report.get("status")
    if st == "stale":
        why = f"SPY'in son gunluk bari {report.get('asof')} - veri bayat"
    elif st == "insufficient":
        why = (f"yalniz {len(report['rows'])}/{report['universe_size']} tema "
               f"ETF'inin verisi geldi (en az {report['min_valid']} gerekir)")
    else:
        why = "SPY (kiyas) verisi alinamadi"
    return (f"TEMA RADARI | UYARI: {why} -> bugun siralama ve isaret "
            "URETILMEDI (uydurma yok). Veri gelince kendiliginden devam eder; "
            "bu kesinti icin tekrar uyari gonderilmez.")


def _iso_week(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


class ThemeRadar:
    """Durumlu sarmalayici: hesap + kalici durum + gonderilecek metinler.
    Telegram'a KENDISI gondermez; metinleri scheduler kendi kanalindan
    yollar (test edilebilirlik + kanal kurali tek yerde)."""

    _META_KEY = "theme_radar_state"

    def __init__(self, universe_spec: str, params: RadarParams = RadarParams(),
                 db=None) -> None:
        self.universe = parse_universe(universe_spec)
        self.params = params
        self._db = db
        self.state: dict = self._load()

    @property
    def symbols(self) -> list[str]:
        return [BENCH] + [s for s, _ in self.universe]

    @property
    def last_report(self) -> dict | None:
        return self.state.get("last_report")

    def last_run_date(self) -> date | None:
        raw = self.state.get("last_run")
        try:
            return date.fromisoformat(raw) if raw else None
        except ValueError:
            return None

    def _load(self) -> dict:
        if self._db is None:
            return {}
        try:
            row = self._db.query_one(
                "SELECT value FROM meta WHERE key=?", (self._META_KEY,))
            if row and row["value"]:
                return json.loads(row["value"])
        except Exception:
            log.exception(kv(event="theme_radar_restore_failed"))
        return {}

    def _persist(self) -> None:
        if self._db is None:
            return
        try:
            self._db.execute(
                "INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)",
                (self._META_KEY, json.dumps(self.state)))
        except Exception:
            log.exception(kv(event="theme_radar_persist_failed"))

    def run(self, daily: dict, today: date) -> list[str]:
        """Bir gunluk kosum. Donus: Telegram'a gidecek metinler (sirali)."""
        report = compute_report(daily, self.universe, today, self.params)
        st = json.loads(json.dumps(self.state))
        messages: list[str] = []
        events: list[dict] = []
        if report["status"] != "ok":
            if not st.get("outage"):
                messages.append(render_outage(report))
            st["outage"] = True
        else:
            if st.get("outage"):
                messages.append("TEMA RADARI | veri geri geldi - olcum "
                                "normal akisa dondu.")
            st["outage"] = False
            events, st = evaluate_signals(report, st, self.params, today)
            week = _iso_week(today)
            if st.get("weekly_week") != week:
                messages.append(render_weekly(
                    report, st.get("weekly_ranks") or {}, st.get("hot") or {}))
                st["weekly_week"] = week
                st["weekly_ranks"] = {r["symbol"]: r["rank"]
                                      for r in report["rows"]}
            for e in events:
                if e["type"] == "heating":
                    messages.append(render_heating(e["row"], report))
                else:
                    messages.append(render_cooling(e["row"], e["since"], report))
        st["last_run"] = today.isoformat()
        st["last_report"] = report
        st["last_events"] = [{"type": e["type"], "symbol": e["row"]["symbol"]}
                             for e in events]
        self.state = st
        self._persist()
        log.info(kv(event="theme_radar_run", status=report["status"],
                    asof=report["asof"], valid=len(report["rows"]),
                    missing=len(report["missing"]), events=len(events),
                    messages=len(messages)))
        return messages

    def preview(self, daily: dict, today: date) -> dict:
        """Durumu DEGISTIRMEDEN hesap: rapor + bugun kosulsa cikacak
        isaretler. Kalici durum (sicak liste, haftalik damga) yazilmaz."""
        report = compute_report(daily, self.universe, today, self.params)
        events, _ = evaluate_signals(report, self.state, self.params, today)
        return {"dry": True, "report": report,
                "would_alert": [{"type": e["type"],
                                 "symbol": e["row"]["symbol"]}
                                for e in events]}

    def summary(self) -> dict:
        """/theme-radar ucu icin."""
        return {"report": self.last_report,
                "hot": self.state.get("hot") or {},
                "last_alert": self.state.get("last_alert") or {},
                "last_events": self.state.get("last_events") or [],
                "last_run": self.state.get("last_run"),
                "weekly_week": self.state.get("weekly_week"),
                "outage": bool(self.state.get("outage")),
                "universe": [{"symbol": s, "label": lbl}
                             for s, lbl in self.universe]}
