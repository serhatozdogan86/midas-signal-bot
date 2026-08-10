"""
Flask HTTP katmani (Faz 1).
Cekirdek: /healthz /status /scan /scan/dry /universe /watchlist /regime\nFaz 3: /dashboard (izleme ekrani), /performance /signals (golge takip),\n       /backup/info /backup/now (gist yedekleme durumu + manuel tetik)
/scan/dry: deploy sonrasi dogrulama (plan bolum 7) - Telegram'a mesaj atmadan
tum evreni tarar ve tam contract JSON dondurur; seans saati kontrolune takilmaz.

"""
from __future__ import annotations

import json
import logging
import secrets
import os
import time

from datetime import datetime, timezone

from flask import Flask, jsonify, request, send_from_directory

from app.dashboard import DASHBOARD_HTML
from app.logging_setup import get_ring_buffer, kv
from app.scheduler import Scheduler
from app.services.state_store import StateStore
from app.services.universe import UniverseProvider

log = logging.getLogger("server")


def create_app(store: StateStore, scheduler: Scheduler,
               universe: UniverseProvider, tracker=None,
               gist_backup=None, commentary=None, news=None) -> Flask:
    app = Flask(__name__)

    @app.after_request
    def no_store(resp):
        # Ara katman/istemci onbellegini kapat: dashboard ve /diag her zaman
        # TAZE veri dondurmeli (bayat 10 saatlik /diag vakasi, 2026-07-29).
        resp.headers["Cache-Control"] = "no-store, max-age=0"
        return resp

    # v4.27 SURUM GORUNURLUGU: Faz 1 paralel dogrulamasi "iki taraf ayni
    # kodu mu kosuyor" sorusunu OLCEMIYORDU (10 Agu raporu - kriter 4 farki
    # kod suphesiyle kapatilamadi). engine_sha strateji kodunun parmak izi
    # (kohort damgasiyla ayni deger), commit calisan agacin kimligi
    # (Render'da env'den, VM'de git'ten). Bir kez hesaplanir.
    from app.services import signal_tracker as _st

    def _git_commit() -> str | None:
        c = os.getenv("RENDER_GIT_COMMIT")
        if c:
            return c[:12]
        try:
            import subprocess
            return subprocess.check_output(
                ["git", "rev-parse", "--short=12", "HEAD"],
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                text=True, timeout=3).strip()
        except Exception:
            return None

    _VERSION = {"engine_sha": _st._ENGINE_SHA, "commit": _git_commit()}

    def _build_diag() -> dict:
        """Uzaktan tani sozlesmesi: botun sagligiyla ilgili her sey tek JSON'da.
        Hem /diag ucundan hem dashboard HTML'ine gomulu olarak sunulur ki
        Render log konsoluna girmeden tek URL'den durum okunabilsin."""
        ring = get_ring_buffer()
        diag = {
            "version": _VERSION,
            "now_utc": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "uptime_sec": ring.uptime_sec(),
            "meta": store.get_meta(),
            "regime": scheduler.regime.model_dump(mode="json"),
            "last_scan": scheduler.last_scan_info,
            "last_prep": scheduler.last_prep_info,
            "watchlist": scheduler.watchlist[:15],
            "log_counts": dict(ring.counts),
            "recent_warnings": ring.recent(60),
            "progress": getattr(scheduler, "progress", ""),
        }
        try:
            diag["universe"] = universe.describe() if universe else None
        except Exception:
            diag["universe"] = None
        if tracker is not None:
            try:
                st = tracker.stats()
                diag["shadow"] = {k: st[k] for k in
                                  ("open_signals", "decided_trades", "win_rate",
                                   "total_r_multiple", "closed_by_outcome",
                                   "dataset")}
            except Exception:
                diag["shadow"] = None
        diag["gist"] = gist_backup.info() if gist_backup is not None else None
        diag["market_note"] = scheduler.last_market_note
        diag["gap_watch"] = scheduler.last_gap_watch
        diag["fine_scan"] = getattr(scheduler, "last_fine_info", {})
        try:
            diag["session_guard"] = scheduler.guard_info()
        except Exception:
            diag["session_guard"] = {"error": "guard_info_failed"}
        # v3.16: bilanco takvimi KARAR filtresidir - durumu gorunur olmali
        try:
            diag["telegram"] = scheduler.telegram_status()
        except Exception:
            diag["telegram"] = {"error": "telegram_status_failed"}
        try:
            diag["earnings"] = scheduler._earnings.status()
        except Exception:
            diag["earnings"] = {"error": "earnings_status_failed"}
        # v3.19: cikis laboratuvari karsilastirmasi (V0 canli vs varyantlar)
        try:
            if scheduler._exit_lab is not None:
                diag["exit_lab"] = scheduler._exit_lab.summary()
        except Exception:
            diag["exit_lab"] = {"error": "exit_lab_failed"}
        # v4.24 AYNA (salt olcum, etiketi diag() icinde sabit)
        try:
            mirror = getattr(scheduler, "_mirror", None)
            if mirror is not None:
                diag["mirror"] = mirror.diag()
        except Exception:
            diag["mirror"] = {"error": "mirror_failed"}
        diag["news"] = news.info() if news is not None else None
        try:
            diag["session"] = scheduler.session_info()
            diag["calendar_strip"] = scheduler.build_calendar_strip()
        except Exception:
            diag["session"], diag["calendar_strip"] = None, []
        diag["commentary_latest"] = (commentary.latest()
                                     if commentary is not None else None)
        return diag

    _WALLET_MAX_ROWS = 200

    def _admin_ok() -> bool:
        """Durum degistiren / pahali uclar icin token kontrolu (v3.9.4).
        Neden: GET /scan kimlik dogrulamasiz TAM TARAMA tetikliyor,
        Telegram'a sinyal gonderiyor ve golge deftere kayit aciyordu -
        bir arama motoru/link on-yuklemesi bile kilit kohortunu
        kirletebilirdi. Salt-okunur uclar (dashboard besleyenler) ACIK
        kalir; yalniz yan etkili/pahali olanlar korunur."""
        tok = getattr(scheduler._settings, "ADMIN_TOKEN", "")
        if not tok:
            return False        # tanimsizsa GUVENLI TARAF: kapali
        given = (request.headers.get("X-Admin-Token")
                 or request.args.get("token") or "")
        return secrets.compare_digest(str(given), str(tok))

    def _admin_denied():
        if not getattr(scheduler._settings, "ADMIN_TOKEN", ""):
            return jsonify({"error": "ADMIN_TOKEN tanimli degil - bu uc kapali. "
                                     "Render ortam degiskenlerine ekleyin."}), 503
        return jsonify({"error": "yetkisiz"}), 401

    @app.get("/kullanici-el-kitabi.pdf")
    def handbook_pdf():
        """Strateji/mekanizma kullanici el kitabi (PDF). app/static altinda
        saklanir; dashboard sol menusundeki 'Kullanım Kılavuzu' baglantisi
        buraya cikar."""
        static_dir = os.path.join(app.root_path, "static")
        return send_from_directory(static_dir, "kullanici-el-kitabi.pdf",
                                    mimetype="application/pdf")

    @app.get("/")
    @app.get("/dashboard")
    def dashboard():
        # Uzaktan tani: HTML sadelestiricileri <script> icerigini attigi icin
        # durum ozeti GORUNUR metin olarak + /diag'a TAM ADRESLI link olarak
        # gomulur. Boylece sayfayi ceken bir arac (or. Claude) once ozeti okur,
        # detay icin linkteki ham JSON'a gecebilir.
        diag = _build_diag()
        last = diag.get("last_scan") or {}
        prep = diag.get("last_prep") or {}
        shadow = diag.get("shadow") or {}
        diag_url = request.host_url.rstrip("/") + "/diag"
        status_line = (
            f'DURUM OZETI :: '
            f'{("[" + diag["progress"] + "] ") if diag.get("progress") else ""}'
            f'son tarama: {last.get("ts_utc", "henuz yok")}'
            f' | taranan: {last.get("scanned", 0)}'
            f' | sinyal: {last.get("signals", 0)}'
            f' | 1h aday/alinan: {last.get("hourly_candidates", 0)}'
            f'/{last.get("hourly_received", 0)}'
            f' | sure: {last.get("duration_s", "-")}s'
            f' | evren: {prep.get("universe", "-")}'
            f' | rejim: {diag["regime"].get("regime", "-")}'
            f' | golge acik/sonuclanan: {shadow.get("open_signals", 0)}'
            f'/{shadow.get("decided_trades", 0)}'
            f' | uyari/hata: {diag["log_counts"]["WARNING"]}'
            f'/{diag["log_counts"]["ERROR"]}'
            f' | uptime: {diag["uptime_sec"] // 60}dk'
            f' | detay: <a href="{diag_url}">{diag_url}</a>'
            f' | log: <a href="{request.host_url.rstrip("/")}/dx">'
            f'{request.host_url.rstrip("/")}/dx</a>')
        payload = json.dumps(diag, ensure_ascii=True).replace("</", "<\\/")
        tape = f'<div class="tape">{status_line}</div>'
        html = DASHBOARD_HTML
        idx = html.find("<!--TAPE-->")
        if idx >= 0:
            # v4 dersi (1 Agu): yer tutucu bundler'in JSON sablon yukunun
            # ICINDE olabilir - ham HTML basmak JSON'u kirar ("Error
            # unpacking ... position 44657"). Script icindeyse fragment
            # JSON-kacisli (ve </script> kacisi icin \u002F'li) basilir.
            in_script = (html.rfind("<script", 0, idx)
                         > html.rfind("</script>", 0, idx))
            frag = (json.dumps(tape)[1:-1].replace("/", "\\u002F")
                    if in_script else tape)
            html = html.replace("<!--TAPE-->", frag)
        else:                                   # eski sablon yedegi
            html = html.replace("</body>", tape + "</body>")
        html = html.replace(
            "</body>",
            f'<script type="application/json" id="server-diag">{payload}</script>'
            f"</body>")
        return app.response_class(html, mimetype="text/html")

    @app.get("/dx")
    def dx():
        """Duz metin tani: basliklar + son uyari/hata loglari.
        /diag'in kenar-onbellek zehirlenmesine karsi taze dogan yedek kanal."""
        ring = get_ring_buffer()
        d = _build_diag()
        last = d.get("last_scan") or {}
        lines = [
            f"now={d['now_utc']} uptime_min={d['uptime_sec'] // 60}",
            f"scan_last={last.get('ts_utc')} scanned={last.get('scanned')} "
            f"signals={last.get('signals')} dur_s={last.get('duration_s')}",
            f"regime={d['regime'].get('regime')} "
            f"universe={d.get('universe', {}).get('filtered_count') if d.get('universe') else '-'} "
            f"shadow_open={d.get('shadow', {}).get('open_signals') if d.get('shadow') else '-'}",
            f"progress={d.get('progress') or '-'}",
            f"warn={ring.counts['WARNING']} err={ring.counts['ERROR']}",
            "--- son kayitlar (WARNING+) ---",
        ]
        for r in ring.recent(40):
            lines.append(f"{r['ts']} {r['level']} {r['logger']}: {r['msg']}")
        return app.response_class("\n".join(lines), mimetype="text/plain")

    @app.get("/diag")
    def diag():
        return app.response_class(json.dumps(_build_diag(), indent=2),
                                  mimetype="application/json")

    # --------------------------------------------- golge takip (Faz 3)
    @app.get("/performance")
    def performance():
        if tracker is None:
            return jsonify({"error": "shadow tracking disabled"}), 404
        stats = tracker.stats()
        stats["benchmark"] = scheduler.benchmark_info()   # SPY ayni donem
        stats["net"] = tracker.net_totals()               # maliyet sonrasi
        stats["phases"] = tracker.phase_breakdown()       # seans fazi dokumu
        return app.response_class(json.dumps(stats, indent=2),
                                  mimetype="application/json")

    @app.get("/signals")
    def signals():
        if tracker is None:
            return jsonify({"error": "shadow tracking disabled"}), 404
        limit = int(request.args.get("limit", "100"))
        return app.response_class(
            json.dumps(tracker.recent_signals(limit), indent=2),
            mimetype="application/json")

    @app.get("/live")
    def live():
        """Aksiyon Paneli: acik sinyallerin canli fiyatla durumu."""
        return app.response_class(
            json.dumps({"rows": scheduler.get_live_status(),
                        "indices": scheduler.index_pulse(),
                        "session": scheduler.session_info()}, indent=2),
            mimetype="application/json")

    @app.get("/candles")
    def candles():
        if tracker is None:
            return jsonify({"error": "shadow tracking disabled"}), 404
        symbol = request.args.get("symbol", "").upper()
        interval = request.args.get("interval", "1h")
        limit = int(request.args.get("limit", "80"))
        rows = tracker.export_candles(symbol, interval)[-limit:]
        return app.response_class(json.dumps(rows), mimetype="application/json")

    @app.get("/news")
    def news_feed():
        if news is None:
            return jsonify({"error": "news disabled (FINNHUB_API_KEY not set)"}), 404
        return app.response_class(
            json.dumps({"info": news.info(), "items": news.items(40)},
                       indent=2), mimetype="application/json")

    @app.get("/commentary")
    def commentary_list():
        if commentary is None:
            return jsonify({"error": "commentary disabled"}), 404
        return app.response_class(
            json.dumps(commentary.recent(10), indent=2),
            mimetype="application/json")

    # --------------------------------------------- gist yedekleme (Faz 3)
    @app.get("/backup/info")
    def backup_info():
        if gist_backup is None:
            return jsonify({"error": "gist sync disabled (GITHUB_TOKEN not set)"}), 404
        info = gist_backup.info()
        # v4.28 GUVENLIK (10 Agu Faz 1 bulgusu): gist "secret"tir ama
        # URL'yi bilen HERKES okur - kimligi kimliksiz bir uctan vermek
        # sinyal gecmisini fiilen herkese acmakti. Kimlik yalniz admin'e;
        # pano/denetim icin gereken tazelik alanlari aciktir.
        if not _admin_ok():
            info.pop("gist_id", None)
            info.pop("gist_url", None)
            info["gist_id_redacted"] = True
        return jsonify(info)

    @app.post("/backup/now")
    def backup_now():
        if not _admin_ok():
            return _admin_denied()
        if gist_backup is None:
            return jsonify({"error": "gist sync disabled (GITHUB_TOKEN not set)"}), 404
        ok = gist_backup.sync()
        return jsonify({"synced": ok, **gist_backup.info()}), (200 if ok else 502)

    # ---- v4 pano uyumluluk uclari (bybit sablonunun bekledigi sekiller) ----
    @app.get("/prices")
    def live_prices():
        """{SYM: fiyat} - acik/bekleyen sinyaller + endeksler."""
        out = {}
        try:
            # NOT: get_live_status() LISTE dondurur (zarfi /live rotasi kurar)
            for r in scheduler.get_live_status():
                if r.get("quote") is not None:
                    out[r["symbol"]] = r["quote"]
            for ix in scheduler.index_pulse():
                if ix.get("price") is not None:
                    out[ix["symbol"]] = ix["price"]
        except Exception:
            log.exception(kv(event="prices_failed"))
        return jsonify({"prices": out})

    @app.get("/market")
    def market_metrics():
        """Piyasa nabzi: endeksler, genislik, yukselen/dusen, rejim okumasi.
        Kripto sablonundaki 'majors/fng/breadth' alanlari hisse dunyasina
        esleniyor (fng yerine REJIM, funding yerine not)."""
        try:
            rows_all = scheduler.get_live_status()
            reg = scheduler.regime.model_dump(mode="json")
            majors = [{"symbol": ix["symbol"], "last": ix.get("price"),
                       "pct24h": ix.get("pct"),
                       "note": "endeks"} for ix in scheduler.index_pulse()]
            rows = [r for r in rows_all if r.get("quote") is not None]
            movers = []
            for r in rows:
                q, e = r.get("quote"), r.get("fill_price") or r.get("entry_max")
                if q and e:
                    movers.append({"symbol": r["symbol"],
                                   "pct24h": round((q / e - 1) * 100, 2)})
            movers.sort(key=lambda x: x["pct24h"], reverse=True)
            adv = sum(1 for m in movers if m["pct24h"] > 0)
            uni = universe.describe() if universe is not None else {}
            return jsonify({
                "updated_utc": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"),
                "majors": majors,
                "fng": {"value": None, "label_tr": reg.get("regime", "-")},
                "breadth": {"advancers": adv,
                            "decliners": max(0, len(movers) - adv)},
                "liquid_universe": uni.get("filtered_count", 0),
                "gainers": movers[:5], "losers": movers[-5:][::-1],
                "pulse": reg.get("detail") or reg.get("regime")})
        except Exception:
            log.exception(kv(event="market_failed"))
            return jsonify({"error": "market info unavailable"}), 503

    # ---- ikon + manifest (sablon bunlari cagiriyordu ama 404'tu) ----
    _ICON_SVG = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><defs><linearGradient id='f' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='#1B0F30'/><stop offset='1' stop-color='#0B0616'/></linearGradient></defs><rect width='32' height='32' rx='8' fill='url(#f)'/><rect x='1.2' y='1.2' width='29.6' height='29.6' rx='7' fill='none' stroke='#B18AFF' stroke-width='1.4' opacity='.85'/><g stroke='#B18AFF' stroke-width='.6' opacity='.18'><path d='M3 11h26M3 16h26M3 21h26'/></g><path d='M6 21.5l5.5-6.5 4 4.2 3-4 3.5 3.2 4-9.4' fill='none' stroke='#FF3DA6' stroke-width='2.6' stroke-linecap='round' stroke-linejoin='round' opacity='.55' transform='translate(-1,.6)'/><path d='M6 21.5l5.5-6.5 4 4.2 3-4 3.5 3.2 4-9.4' fill='none' stroke='#35E7FF' stroke-width='2.6' stroke-linecap='round' stroke-linejoin='round' opacity='.5' transform='translate(1,-.6)'/><path d='M6 21.5l5.5-6.5 4 4.2 3-4 3.5 3.2 4-9.4' fill='none' stroke='#5BE49B' stroke-width='2.6' stroke-linecap='round' stroke-linejoin='round'/><circle cx='26' cy='8.8' r='2.6' fill='#5BE49B'/><circle cx='26' cy='8.8' r='4.6' fill='none' stroke='#5BE49B' stroke-width='.9' opacity='.35'/></svg>")

    @app.get("/icon.svg")
    def icon_svg():
        return app.response_class(_ICON_SVG, mimetype="image/svg+xml",
                                  headers={"Cache-Control": "public, max-age=86400"})

    @app.get("/manifest.webmanifest")
    def web_manifest():
        return jsonify({
            "name": "MIDAS SINYAL", "short_name": "MIDAS",
            "description": "ABD hisseleri swing sinyal botu - golge mod",
            "start_url": "/dashboard", "display": "standalone",
            "background_color": "#12091F", "theme_color": "#12091F",
            "icons": [{"src": "/icon.svg", "sizes": "any",
                       "type": "image/svg+xml", "purpose": "any maskable"}],
        })

    @app.get("/audit")
    def audit_view():
        """OZ-DENETIM: degismezlerin canli sonucu. Bozulan varsa
        'failed' > 0 doner ve her kontrol NE YAPILACAGINI soyler."""
        try:
            from app.services.self_audit import run_audit
            from app.services.signal_tracker import _ENGINE_SHA
            rep = run_audit(
                db=tracker._db if tracker else None,
                tracker=tracker, universe=universe,
                earnings=getattr(scheduler, "_earnings", None),
                gist=gist_backup,
                exit_lab=getattr(scheduler, "_exit_lab", None),
                strategy_lab=getattr(scheduler, "_strategy_lab", None),
                engine_sha=_ENGINE_SHA,
                settings=getattr(scheduler, "_settings", None),
                telegram=scheduler.telegram_status())
            return jsonify(rep.to_dict())
        except Exception:
            log.exception(kv(event="audit_failed"))
            return jsonify({"error": "audit unavailable"}), 503

    @app.get("/volatility")
    def volatility_view():
        """Evren genelinde ATR yuzdesi dagilimi + acik pozisyonlarimizin
        yeri. Neden: sinyal kalitesini gozle degerlendirmek icin
        "bu hisse evrene gore ne kadar oynak" sorusunun cevabi lazim.
        Gunluk onbellekten hesaplanir; onbellek bossa 'pending'."""
        try:
            daily = getattr(scheduler, "_daily_cache", None) or {}
            if not daily:
                return jsonify({"pending": True,
                                "note": "gunluk veri henuz yuklenmedi"})
            from app.services.strategy_lab import atr as _atr
            vals = {}
            for sym, series in daily.items():
                cs = series.candles
                if len(cs) < 20:
                    continue
                bars = [{"high": c.high, "low": c.low, "close": c.close}
                        for c in cs[-60:]]
                a14 = _atr(bars)
                last, px = a14[-1], bars[-1]["close"]
                if last and px:
                    vals[sym] = round(100 * last / px, 2)
            if not vals:
                return jsonify({"pending": True, "note": "hesaplanamadi"})
            ordered = sorted(vals.values())
            n = len(ordered)

            def pct(q):
                return ordered[min(n - 1, max(0, int(q * n)))]
            # dagilim kovalari (yuzde ATR)
            edges = [0, 1, 1.5, 2, 3, 4, 6, 100]
            buckets = []
            for i in range(len(edges) - 1):
                lo, hi = edges[i], edges[i + 1]
                buckets.append({"lo": lo, "hi": hi,
                                "n": sum(1 for v in ordered if lo <= v < hi)})
            top = sorted(vals.items(), key=lambda kv: -kv[1])[:5]
            calm = sorted(vals.items(), key=lambda kv: kv[1])[:5]
            ours = []
            try:
                for r in scheduler.get_live_status():
                    sym = r.get("symbol")
                    if sym in vals:
                        ours.append({"symbol": sym, "atr_pct": vals[sym],
                                     "status": r.get("status")})
            except Exception:
                pass
            return jsonify({
                "count": n, "median": pct(0.5), "p10": pct(0.1),
                "p90": pct(0.9), "buckets": buckets,
                "most_volatile": [{"symbol": k, "atr_pct": v} for k, v in top],
                "calmest": [{"symbol": k, "atr_pct": v} for k, v in calm],
                "ours": ours})
        except Exception:
            log.exception(kv(event="volatility_failed"))
            return jsonify({"error": "volatility unavailable"}), 503

    @app.get("/strategy-lab")
    def strategy_lab_view():
        """KATMAN 2: bagimsiz aday GIRIS stratejileri.
        kohort = lab_start sonrasi (karar buna gore verilir),
        tarihsel = 2 yillik referans (BACKTEST, canli kanit degil)."""
        try:
            lab = getattr(scheduler, "_strategy_lab", None)
            if lab is None:
                return jsonify({"error": "strategy lab disabled"}), 404
            if not lab.last:
                return jsonify({"pending": True,
                                "note": "ilk gun sonu kosumunda dolar"})
            return jsonify(lab.last)
        except Exception:
            log.exception(kv(event="strategy_lab_view_failed"))
            return jsonify({"error": "strategy lab unavailable"}), 503

    @app.get("/challengers")
    def challengers_view():
        """ADAYLAR = cikis laboratuvari (V0/V1/V2). Sablonun bekledigi
        'strategies' sekline cevrilir; CI yok (n kucuk) -> None."""
        try:
            if scheduler._exit_lab is None:
                return jsonify({"error": "exit lab disabled"}), 404
            lab = scheduler._exit_lab.summary()
            strategies = {}
            for k, v in (lab.get("variants") or {}).items():
                dec = v.get("n_decided", 0)
                strategies[k] = {
                    "open": v.get("open", 0), "decided": dec, "expired": 0,
                    "win_rate": (v["wins"] / dec) if dec else None,
                    "net_r": v.get("net_r", 0.0),
                    "clusters": dec, "ci": None}
            return jsonify({"strategies": strategies, "faz1_target": 60,
                            "lab_start": lab.get("lab_start")})
        except Exception:
            log.exception(kv(event="challengers_failed"))
            return jsonify({"error": "challengers unavailable"}), 503

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok", **store.get_meta()})

    @app.get("/status")
    def status():
        # v4.2: strateji karti SABIT METIN yerine canli ayarlardan
        # beslensin (pano bybit'ten gelen "BTC 4H rejimi / 4H->15m"
        # degerlerini gosteriyordu - bizim motorumuzla ilgisi yoktu).
        cfg = {}
        try:
            st = scheduler._settings
            cfg = {"risk_reward_min": st.RISK_REWARD_MIN,
                   "volume_mult": st.VOLUME_MULT,
                   "earnings_blackout_days": st.EARNINGS_BLACKOUT_DAYS,
                   "time_stop_days": st.TIME_STOP_DAYS,
                   "htf": st.HTF, "mtf": st.MTF,
                   "max_daily_signals": st.MAX_DAILY_SIGNALS,
                   "max_open_signals": st.MAX_OPEN_SIGNALS}
        except Exception:
            log.exception(kv(event="status_cfg_failed"))
        payload = {"meta": {**store.get_meta(), **cfg},
                   "regime": scheduler.regime.model_dump(mode="json"),
                   "results": store.get_results()}
        return app.response_class(json.dumps(payload, indent=2),
                                  mimetype="application/json")

    @app.get("/scan")
    def scan():
        if not _admin_ok():
            return _admin_denied()
        results = scheduler.run_coarse_scan(send_telegram=True)
        return jsonify([
            {"symbol": d.symbol, "decision": d.decision.value,
             "direction": d.direction.value, "reason": d.reject_reason}
            for d in results
        ])

    @app.get("/scan/dry")
    def scan_dry():
        if not _admin_ok():
            return _admin_denied()
        results = scheduler.run_coarse_scan(send_telegram=False)
        return app.response_class(
            json.dumps([d.contract_dict() for d in results], indent=2),
            mimetype="application/json")

    _qcache: dict = {}

    @app.get("/data-compare")
    def data_compare():
        """Asama 0 teshis ucu: son yfinance<->Alpaca karsilastirma raporu.
        Alpaca anahtari tanimli degilse enabled=false doner."""
        svc = getattr(scheduler, "data_comparison", None)
        if svc is None or not svc.enabled:
            return jsonify({"enabled": False,
                            "note": "ALPACA_API_KEY/SECRET tanimli degil"})
        return jsonify({"enabled": True, "report": svc.last_report})

    @app.post("/wallet")
    def wallet_sync():
        """Dashboard cuzdanini sunucuya aynalar. Amac: localStorage'in
        calismadigi/silindigi durumlarda (1 Agu geri bildirimi - sayfa
        yenilenince veri kayboluyordu) GET /wallet ile geri kurtarma imkani.
        Tam satirlari (sembol+adet+giris+hedef) saklar - yalniz adet degil,
        boylece geri yuklemede K/Z hesabi da dogru kurulur."""
        body = request.get_json(silent=True) or {}
        rows_in = body.get("rows")
        if rows_in is None:
            legacy = body.get("symbols") or {}   # eski istemci (v4.3-v4.9) uyumu
            rows_in = [{"s": k, "q": v} for k, v in legacy.items()]
        # v3.9.4: girdi boyutu sinirli - /wallet panodan cagrildigi icin
        # token koyulamaz; bunun yerine satir sayisi ve alan uzunlugu
        # tavanlanir (sinirsiz liste bellekte buyuyebilirdi).
        if not isinstance(rows_in, list):
            rows_in = []
        rows_in = rows_in[:_WALLET_MAX_ROWS]
        clean = []
        qty_map: dict = {}
        for r in rows_in or []:
            try:
                sym = str(r.get("s") or "").upper().strip()[:12]
                qty = int(r.get("q") or 0)
                entry = float(r.get("e") or 0)
            except (TypeError, ValueError, AttributeError):
                continue
            if not sym or qty <= 0:
                continue
            tgt = r.get("t")
            try:
                tgt = float(tgt) if tgt not in (None, "") else None
            except (TypeError, ValueError):
                tgt = None
            clean.append({"s": sym, "q": qty, "e": entry, "t": tgt})
            qty_map[sym] = qty_map.get(sym, 0) + qty
        scheduler.wallet_rows = clean
        scheduler.wallet = qty_map
        return jsonify({"ok": True, "count": len(clean)})

    @app.get("/wallet")
    def wallet_get():
        """Cuzdan yedek kurtarma: dashboard localStorage bossa buradan
        okur (son basarili POST /wallet anlik goruntusu, bellek-ici)."""
        return jsonify({"rows": getattr(scheduler, "wallet_rows", [])})

    from app.services.fundamentals_service import FundamentalsService
    # v3.9.1: Finnhub istemcisi enjekte edilir (Yahoo .info Render'da
    # engelli). Istemci yoksa servis yfinance yedegine duser.
    _fund_svc = FundamentalsService(
        finnhub=getattr(getattr(scheduler, "_md", None), "_finnhub", None))

    @app.get("/fundamentals")
    def fundamentals():
        """Sirket temel verileri (sektor, F/K, PD/DD, borc/ozkaynak, FAVOK
        marji). Sinyal motoruna karismaz - dashboard karti icin bilgi amacli."""
        syms = [s.strip().upper() for s in
                (request.args.get("symbols") or "").split(",") if s.strip()][:20]
        known = _known_symbols()          # v4.24: kota korumasi (bkz. /quotes)
        if known:
            syms = [s for s in syms if s in known]
        return jsonify(_fund_svc.get_many(syms))

    def _known_symbols() -> set:
        """v4.24 beyaz liste: evren + acik/izlenen sinyaller + cuzdan +
        endeksler. /quotes ve /fundamentals kimliksiz uclardir; keyfi
        sembol kabul etmek disaridan Finnhub kotasini tuketebilir ve
        index_pulse bos kalinca kill-switch (belgeli fail-open istisnasi
        geregi) SESSIZCE korlesirdi - botun tek freni dis istekle
        koreltilebilirdi. Liste bos donerse (restart ani) filtre uygulanmaz
        (panoyu kirmamak icin bilinçli yumusak taraf)."""
        allowed: set = set()
        try:
            allowed |= set(getattr(universe, "_filtered", []) or [])
            allowed |= set(getattr(scheduler, "wallet", {}) or {})
            if tracker is not None:
                allowed |= {r["symbol"] for r in tracker._db.query(
                    "SELECT DISTINCT symbol FROM signals WHERE status!='CLOSED'")}
            if allowed:
                # endeksler yalniz gercek liste varken eklenir; yoksa kume
                # bos kalir ve filtre devre disi (yumusak taraf bozulmasin)
                allowed |= {"SPY", "QQQ"}
        except Exception:
            pass
        return allowed

    @app.get("/quotes")
    def quotes():
        """Cuzdan icin toplu canli fiyat (<=20 sembol, 60sn onbellek)."""
        md = getattr(scheduler, "_md", None)
        syms = [s.strip().upper() for s in
                (request.args.get("symbols") or "").split(",") if s.strip()][:20]
        known = _known_symbols()
        if known:
            syms = [s for s in syms if s in known]
        out = {}
        now = time.time()
        # v4.24: onbellek sinirsiz buyuyordu (keyfi sembol + budamasiz dict)
        if len(_qcache) > 1000:
            _qcache.clear()
        for s in syms:
            ts, val = _qcache.get(s, (0, None))
            if now - ts > 60 and md is not None:
                try:
                    val = md.get_quote_change(s)
                except Exception:
                    val = None
                _qcache[s] = (now, val)
            if val:
                out[s] = val
        return jsonify(out)

    @app.get("/universe")
    def universe_info():
        desc = universe.describe()
        desc["symbols"] = sorted(getattr(universe, "_filtered", []) or [])
        return app.response_class(json.dumps(desc, indent=2),
                                  mimetype="application/json")

    @app.get("/watchlist")
    def watchlist():
        return app.response_class(json.dumps(scheduler.watchlist, indent=2),
                                  mimetype="application/json")

    @app.get("/regime")
    def regime():
        return jsonify(scheduler.regime.model_dump(mode="json"))

    return app
