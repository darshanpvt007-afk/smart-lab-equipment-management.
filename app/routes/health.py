"""Health check for the hosting platform: GET /healthz.

Public on purpose (load balancers do not sign in), so it reveals nothing:
200 {"status": "ok"} when the database answers, 503 {"status": "unavailable"}
when it does not. No versions, hostnames or error text.
"""
from flask import Blueprint, current_app, jsonify

from .. import db

bp = Blueprint("health", __name__)


@bp.route("/healthz")
def healthz():
    try:
        db.query_one("SELECT 1 AS ok")
    except Exception:          # noqa: BLE001 - any failure means "not healthy"
        current_app.logger.warning("Health check: database unavailable.")
        return jsonify(status="unavailable"), 503
    return jsonify(status="ok"), 200
