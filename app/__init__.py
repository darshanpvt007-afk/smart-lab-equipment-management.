"""Smart Laboratory Equipment Management System - Review 3 web application.

create_app() builds the Flask application:
  * reads configuration from environment variables (never from code),
  * registers one blueprint per part of the system,
  * adds a simple CSRF check to every form submission,
  * shows friendly pages for 404 / 500 errors.
"""
import os
import secrets
from datetime import date

from flask import Flask, abort, render_template, request, session

from . import db


def create_app(test_config=None):
    app = Flask(__name__)

    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        DB_HOST=os.environ.get("DB_HOST", "localhost"),
        DB_PORT=int(os.environ.get("DB_PORT", "3306")),
        DB_USER=os.environ.get("DB_USER", "root"),
        DB_PASSWORD=os.environ.get("DB_PASSWORD", ""),
        DB_NAME=os.environ.get("DB_NAME", "smart_lab_equipment_db"),
        DB_UNIX_SOCKET=os.environ.get("DB_UNIX_SOCKET", ""),
        # Optional fixed "today" so the demo matches the sample data
        # (e.g. 2026-10-10). Empty means the real current date.
        REFERENCE_DATE=os.environ.get("APP_REFERENCE_DATE", ""),
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    from .routes import (allocations, categories, dashboard, equipment, labs,
                         maintenance, purchases, reports, staff, students,
                         suppliers)
    for module in (dashboard, equipment, allocations, maintenance, students,
                   staff, labs, categories, suppliers, purchases, reports):
        app.register_blueprint(module.bp)

    # ---- CSRF protection: every POST form must carry the session token ----
    def csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(16)
        return session["csrf_token"]

    @app.before_request
    def check_csrf():
        if request.method == "POST" and not app.config.get("TESTING_SKIP_CSRF"):
            sent = request.form.get("csrf_token", "")
            if not sent or sent != session.get("csrf_token"):
                abort(400, "The form has expired. Please reload the page and try again.")

    # ---- values available in every template ----
    @app.context_processor
    def template_globals():
        return {"csrf_token": csrf_token, "today": today(), "reference_date_fixed": bool(app.config["REFERENCE_DATE"])}

    @app.template_filter("money")
    def money(value):
        return "-" if value is None else f"{value:,.2f}"

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(500)
    def error_page(err):
        code = getattr(err, "code", 500) or 500
        message = getattr(err, "description", "Something went wrong.")
        if code == 500:
            message = "An unexpected error occurred. Check that the MySQL server is running."
        return render_template("error.html", code=code, message=message), code

    return app


def today():
    """The application's notion of 'today' (fixed reference date or real date)."""
    from flask import current_app
    fixed = current_app.config.get("REFERENCE_DATE")
    return date.fromisoformat(fixed) if fixed else date.today()
