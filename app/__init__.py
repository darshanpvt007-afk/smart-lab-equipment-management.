"""Smart Laboratory Equipment Management System - web application.

create_app() builds the Flask application:
  * reads configuration from environment variables (never from code) and
    refuses to start in production without the required secrets,
  * registers one blueprint per part of the system,
  * requires sign-in and checks the user's role on every request (auth.py),
  * checks a CSRF token on every form submission,
  * sends security headers and secure cookie settings,
  * shows friendly error pages that never include internal details.
"""
import logging
import os
import secrets
from datetime import date

import click
from flask import Flask, abort, g, render_template, request, session
from werkzeug.middleware.proxy_fix import ProxyFix

from . import db


class ConfigError(RuntimeError):
    """Raised at start-up when production settings are missing or unsafe."""


def env_flag(name, default=False):
    value = os.environ.get(name)
    return default if value is None else value.strip().lower() in ("1", "true", "yes", "on")


# Content-Security-Policy: only this site's own scripts and styles. Inline
# <script> and event handlers are forbidden; 'unsafe-inline' for styles is
# needed only for the width/height style attributes of the dashboard charts.
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; "
       "base-uri 'none'; form-action 'self'; frame-ancestors 'none'")


def load_config(app, test_config):
    production = os.environ.get("APP_ENV", "development").strip().lower() == "production"
    app.config.update(
        APP_ENV="production" if production else "development",
        SECRET_KEY=os.environ.get("SECRET_KEY", ""),
        DB_HOST=os.environ.get("DB_HOST", "localhost"),
        DB_PORT=int(os.environ.get("DB_PORT", "3306")),
        DB_USER=os.environ.get("DB_USER", ""),
        DB_PASSWORD=os.environ.get("DB_PASSWORD", ""),
        DB_NAME=os.environ.get("DB_NAME", "smart_lab_equipment_db"),
        DB_UNIX_SOCKET=os.environ.get("DB_UNIX_SOCKET", ""),
        DB_CONNECT_TIMEOUT=int(os.environ.get("DB_CONNECT_TIMEOUT", "5")),
        DB_SSL_CA=os.environ.get("DB_SSL_CA", ""),        # path to the provider's CA certificate
        # Optional fixed "today" so the demo matches the sample data
        # (e.g. 2026-10-10). Empty means the real current date.
        REFERENCE_DATE=os.environ.get("APP_REFERENCE_DATE", ""),
        # Number of reverse proxies in front of the app (the host's HTTPS
        # load balancer). 0 = trust no X-Forwarded-* headers.
        TRUST_PROXY=int(os.environ.get("TRUST_PROXY", "0")),
        # Cookies: never readable by JavaScript, not sent on cross-site
        # POSTs, and HTTPS-only in production.
        SESSION_COOKIE_NAME="smartlab_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=env_flag("COOKIE_SECURE", default=production),
        SESSION_HOURS=int(os.environ.get("SESSION_HOURS", "8")),
        PREFERRED_URL_SCHEME="https" if production else "http",
        # Every form in this app is small; refuse large bodies early.
        MAX_CONTENT_LENGTH=64 * 1024,
        MAX_FORM_MEMORY_SIZE=64 * 1024,
        MAX_FORM_PARTS=200,
    )
    if test_config:
        app.config.update(test_config)

    if production:
        problems = []
        if app.config.get("TESTING"):
            problems.append("TESTING must not be enabled in production")
        if len(app.config["SECRET_KEY"]) < 32:
            problems.append("SECRET_KEY must be set to a random value of at least 32 characters")
        if not app.config["DB_USER"] or app.config["DB_USER"] == "root":
            problems.append("DB_USER must be set to the least-privilege runtime account, not root")
        if not app.config["DB_PASSWORD"]:
            problems.append("DB_PASSWORD must be set")
        if not app.config["SESSION_COOKIE_SECURE"]:
            problems.append("COOKIE_SECURE must not be disabled in production (HTTPS only)")
        if problems:
            # Names of the settings only; values are never printed.
            raise ConfigError("Refusing to start in production: " + "; ".join(problems) + ".")
    elif not app.config["SECRET_KEY"]:
        # Development only: a throw-away key; sessions end when the app restarts.
        app.config["SECRET_KEY"] = secrets.token_hex(32)
        app.logger.warning("SECRET_KEY is not set; using a temporary key (development only).")
    if not production and not app.config["DB_USER"]:
        app.config["DB_USER"] = "root"          # local development default only


def create_app(test_config=None):
    app = Flask(__name__)
    load_config(app, test_config)
    app.logger.setLevel(logging.INFO)
    if app.config["TRUST_PROXY"] > 0:
        n = app.config["TRUST_PROXY"]
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=n, x_proto=n, x_host=n)

    db.init_app(app)

    from .routes import (allocations, categories, dashboard, equipment, health, labs,
                         maintenance, portal, purchases, reports, requests, staff,
                         students, suppliers, users)
    from .routes import auth as auth_routes
    for module in (dashboard, equipment, allocations, maintenance, students,
                   staff, labs, categories, suppliers, purchases, reports,
                   auth_routes, users, health, portal, requests):
        app.register_blueprint(module.bp)

    # ---- CSRF protection: every POST form must carry the session token ----
    def csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(16)
        return session["csrf_token"]

    @app.before_request
    def check_csrf():
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            sent = request.form.get("csrf_token", "")
            expected = session.get("csrf_token", "")
            if not sent or not expected or not secrets.compare_digest(sent, expected):
                abort(400, "The form has expired. Please reload the page and try again.")

    # ---- sign-in and role check on every request (after the CSRF check) ----
    from . import auth
    auth.init_app(app)

    @app.after_request
    def security_headers(response):
        h = response.headers
        h.setdefault("Content-Security-Policy", CSP)
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "same-origin")
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if app.config["APP_ENV"] == "production":
            h.setdefault("Strict-Transport-Security", "max-age=31536000")
        if g.get("user") is not None and response.mimetype == "text/html":
            # Signed-in pages must not stay in a shared lab PC's browser cache.
            h["Cache-Control"] = "no-store"
        return response

    @app.cli.command("create-user")
    @click.option("--username", prompt=True, help="Lower-case login name, e.g. priya.s")
    @click.option("--role", prompt=True, type=click.Choice(sorted(auth.ROLES)),
                  help="admin, lab_manager, inventory_staff or technician")
    @click.option("--staff-id", type=int, default=None, help="Optional lab_staff.staff_id")
    @click.option("--password-stdin", is_flag=True,
                  help="Read the password from standard input instead of prompting.")
    def create_user_command(username, role, staff_id, password_stdin):
        """Create a sign-in account (use it for the first administrator).
        The password is asked for twice and never echoed or logged."""
        import sys
        username = username.strip().lower()
        if password_stdin:
            password = sys.stdin.readline().rstrip("\n")
        else:
            password = click.prompt("Password", hide_input=True, confirmation_prompt=True)
        errors = auth.validate_new_account(username, role, password, staff_id)
        if errors:
            raise click.ClickException(" ".join(errors.values()))
        if db.query_one("SELECT 1 AS x FROM app_user WHERE username = %s", (username,)):
            raise click.ClickException(f"Account {username} already exists.")
        auth.insert_user(username, role, password, staff_id)
        click.echo(f"Created account {username} with role {role}.")

    @app.cli.command("seed-accounts")
    @click.option("--out", "out_path", type=click.Path(dir_okay=False),
                  default=lambda: os.path.join(os.path.expanduser("~"), "smartlab-credentials.csv"),
                  show_default="~/smartlab-credentials.csv",
                  help="Private file that receives the generated passwords (must not exist yet).")
    @click.option("--reset", is_flag=True,
                  help="Also give EXISTING accounts a new password (they are signed out).")
    def seed_accounts_command(out_path, reset):
        """Create the ready-made accounts: 3 administrators, 3 lab teachers and
        one account per student. Passwords are generated, written only to the
        --out file (permissions 600) and never shown here."""
        from . import seed
        out_path = os.path.abspath(out_path)
        if os.path.exists(out_path):
            raise click.ClickException(f"{out_path} already exists; move it away or pass --out.")
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            inside_repo = os.path.commonpath([out_path, repo]) == repo
        except ValueError:                      # different drives on Windows
            inside_repo = False
        if inside_repo:
            raise click.ClickException("Write the credentials file outside the project folder, "
                                       "so it can never be committed.")
        summary = seed.seed_accounts(out_path, reset=reset)
        for kind, login, name, role, action in summary:
            click.echo(f"{action:15} {login:17} {name:18} {role}")
        if os.path.exists(out_path):
            click.echo(f"\nPasswords saved to {out_path} (readable only by you). "
                       "Hand each person their own line, then delete or move the file.")
        else:
            click.echo("\nAll accounts already existed; nothing changed (use --reset for new passwords).")

    # ---- values available in every template ----
    @app.context_processor
    def template_globals():
        return {"csrf_token": csrf_token, "today": today(), "nav_counts": nav_counts,
                "reference_date_fixed": bool(app.config["REFERENCE_DATE"])}

    @app.template_filter("money")
    def money(value):
        return "-" if value is None else f"{value:,.2f}"

    @app.template_filter("inr")
    def inr(value):
        """Whole rupees for summaries, e.g. 9700 -> '₹9,700'."""
        return "₹0" if value is None else f"₹{value:,.0f}"

    @app.template_filter("dmy")
    def dmy(value, year=True):
        """2026-10-07 -> '7 Oct 2026' (or '7 Oct' with year=False)."""
        if value is None:
            return "-"
        if isinstance(value, str):          # dates read through a UNION come back as text
            value = date.fromisoformat(value[:10])
        return f"{value.day} {value:%b}" + (f" {value.year}" if year else "")

    ERROR_MESSAGES = {
        401: "Please sign in to continue.",
        403: "Your account is not allowed to do this. Ask an administrator if you need access.",
        405: "This action is not allowed here.",
        413: "The request is too large.",
        429: "Too many requests. Please wait and try again.",
        500: "An unexpected error occurred. Please try again; if it continues, tell the administrator.",
    }

    @app.errorhandler(400)
    @app.errorhandler(401)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(405)
    @app.errorhandler(413)
    @app.errorhandler(429)
    @app.errorhandler(500)
    def error_page(err):
        code = getattr(err, "code", 500) or 500
        if code in ERROR_MESSAGES:
            # Fixed text only: no exception details, SQL or settings reach the page.
            message = ERROR_MESSAGES[code]
        else:
            message = getattr(err, "description", "Something went wrong.")
        return render_template("error.html", code=code, message=message), code

    return app


def nav_counts():
    """Live figures for the sidebar. Called from base.html; returns {} if the
    database cannot be reached so that error pages still render."""
    try:
        return db.query_one(
            "SELECT (SELECT COUNT(*) FROM equipment) AS equipment, "
            "       (SELECT COUNT(*) FROM maintenance WHERE maintenance_status <> 'Completed') AS open_jobs, "
            "       (SELECT COUNT(*) FROM equipment_allocation "
            "         WHERE allocation_status = 'Issued' AND expected_return_date < %s) AS overdue, "
            "       (SELECT COUNT(*) FROM student) AS students, "
            "       (SELECT COUNT(*) FROM lab_staff) AS staff, "
            "       (SELECT COUNT(*) FROM purchase WHERE purchase_status = 'Ordered') AS open_orders, "
            "       (SELECT COUNT(*) FROM equipment_request WHERE request_status = 'Pending') AS pending_requests",
            (today(),)) or {}
    except Exception:          # noqa: BLE001 - the sidebar must never break a page
        return {}


def today():
    """The application's notion of 'today' (fixed reference date or real date)."""
    from flask import current_app
    fixed = current_app.config.get("REFERENCE_DATE")
    return date.fromisoformat(fixed) if fixed else date.today()
