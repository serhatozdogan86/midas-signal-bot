"""
Flask HTTP katmani (Faz 1).
Cekirdek: /healthz /status /scan /scan/dry /universe /watchlist /regime
/scan/dry: deploy sonrasi dogrulama (plan bolum 7) - Telegram'a mesaj atmadan
tum evreni tarar ve tam contract JSON dondurur; seans saati kontrolune takilmaz.
Dashboard uyarlamasi Phase 3.
"""
from __future__ import annotations

import json

from flask import Flask, jsonify

from app.scheduler import Scheduler
from app.services.state_store import StateStore
from app.services.universe import UniverseProvider


def create_app(store: StateStore, scheduler: Scheduler,
               universe: UniverseProvider) -> Flask:
    app = Flask(__name__)

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
