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
from app.scheduler import Scheduler
from app.services.state_store import StateStore
from app.services.universe import UniverseProvider


def create_app(store: StateStore, scheduler: Scheduler,
               universe: UniverseProvider, tracker=None,
               gist_backup=None) -> Flask:
    app = Flask(__name__)

    @app.get("/")
    @app.get("/dashboard")
    def dashboard():
        return app.response_class(DASHBOARD_HTML, mimetype="text/html")

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
