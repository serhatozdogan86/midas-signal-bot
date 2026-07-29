"""
Flask HTTP katmani (Faz 1).
Cekirdek: /healthz /status /scan /scan/dry /universe /watchlist /regime\nFaz 3: /dashboard (izleme ekrani), /performance /signals (golge takip),\n       /backup/info /backup/now (gist yedekleme durumu + manuel tetik)
/scan/dry: deploy sonrasi dogrulama (plan bolum 7) - Telegram'a mesaj atmadan
tum evreni tarar ve tam contract JSON dondurur; seans saati kontrolune takilmaz.

"""
from __future__ import annotations

import json

from flask import Flask, jsonify, request

from app.dashboard import DASHBOARD_HTML
from app.logging_setup import get_ring_buffer
from app.scheduler import Scheduler
from app.services.state_store import StateStore
from app.services.universe import UniverseProvider


def create_app(store: StateStore, scheduler: Scheduler,
               universe: UniverseProvider, tracker=None,
               gist_backup=None) -> Flask:
    app = Flask(__name__)

    def _build_diag() -> dict:
        """Uzaktan tani sozlesmesi: botun sagligiyla ilgili her sey tek JSON'da.
        Hem /diag ucundan hem dashboard HTML'ine gomulu olarak sunulur ki
        Render log konsoluna girmeden tek URL'den durum okunabilsin."""
        ring = get_ring_buffer()
        diag = {
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
        return diag

    @app.get("/")
    @app.get("/dashboard")
    def dashboard():
        # server-diag blogu: sayfa kaynagindan (JS calismadan) durum okunabilsin
        payload = json.dumps(_build_diag(), ensure_ascii=True).replace("</", "<\\/")
        html = DASHBOARD_HTML.replace(
            "</body>",
            f'<script type="application/json" id="server-diag">{payload}</script></body>')
        return app.response_class(html, mimetype="text/html")

    @app.get("/diag")
    def diag():
        return app.response_class(json.dumps(_build_diag(), indent=2),
                                  mimetype="application/json")

    # --------------------------------------------- golge takip (Faz 3)
    @app.get("/performance")
    def performance():
        if tracker is None:
            return jsonify({"error": "shadow tracking disabled"}), 404
        return app.response_class(json.dumps(tracker.stats(), indent=2),
                                  mimetype="application/json")

    @app.get("/signals")
    def signals():
        if tracker is None:
            return jsonify({"error": "shadow tracking disabled"}), 404
        limit = int(request.args.get("limit", "100"))
        return app.response_class(
            json.dumps(tracker.recent_signals(limit), indent=2),
            mimetype="application/json")

    # --------------------------------------------- gist yedekleme (Faz 3)
    @app.get("/backup/info")
    def backup_info():
        if gist_backup is None:
            return jsonify({"error": "gist sync disabled (GITHUB_TOKEN not set)"}), 404
        return jsonify(gist_backup.info())

    @app.post("/backup/now")
    def backup_now():
        if gist_backup is None:
            return jsonify({"error": "gist sync disabled (GITHUB_TOKEN not set)"}), 404
        ok = gist_backup.sync()
        return jsonify({"synced": ok, **gist_backup.info()}), (200 if ok else 502)

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok", **store.get_meta()})

    @app.get("/status")
    def status():
        payload = {"meta": store.get_meta(),
                   "regime": scheduler.regime.model_dump(mode="json"),
                   "results": store.get_results()}
        return app.response_class(json.dumps(payload, indent=2),
                                  mimetype="application/json")

    @app.get("/scan")
    def scan():
        results = scheduler.run_coarse_scan(send_telegram=True)
        return jsonify([
            {"symbol": d.symbol, "decision": d.decision.value,
             "direction": d.direction.value, "reason": d.reject_reason}
            for d in results
        ])

    @app.get("/scan/dry")
    def scan_dry():
        results = scheduler.run_coarse_scan(send_telegram=False)
        return app.response_class(
            json.dumps([d.contract_dict() for d in results], indent=2),
            mimetype="application/json")

    @app.get("/universe")
    def universe_info():
        return app.response_class(json.dumps(universe.describe(), indent=2),
                                  mimetype="application/json")

    @app.get("/watchlist")
    def watchlist():
        return app.response_class(json.dumps(scheduler.watchlist, indent=2),
                                  mimetype="application/json")

    @app.get("/regime")
    def regime():
        return jsonify(scheduler.regime.model_dump(mode="json"))

    return app
