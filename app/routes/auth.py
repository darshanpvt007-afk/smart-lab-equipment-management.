"""Sign in, sign out and change your own password."""
from flask import (Blueprint, current_app, flash, g, redirect, render_template, request,
                   url_for)

from .. import auth, db

bp = Blueprint("auth", __name__)

LOGIN_FAILED = "Invalid username or password."
LOGIN_BLOCKED = (f"Too many failed sign-in attempts. Wait {auth.WINDOW_MINUTES} minutes "
                 "and try again, or ask an administrator.")


@bp.route("/login", methods=["GET", "POST"])
def login():
    target = auth.safe_next(request.values.get("next")) or url_for("dashboard.index")
    auth.load_user()
    if g.user is not None:
        return redirect(target)
    if request.method == "GET":
        return render_template("auth/login.html", next=request.args.get("next", ""), error=None)

    username = request.form.get("username", "").strip().lower()[:40]
    password = request.form.get("password", "")[:auth.PASSWORD_MAX + 1]
    ip = auth.client_ip()

    def refuse(message, status):
        return render_template("auth/login.html", next=request.form.get("next", ""),
                               error=message, username=username), status

    if not username or not password:
        return refuse(LOGIN_FAILED, 401)
    if auth.login_blocked(username, ip):
        current_app.logger.warning("Sign-in blocked by throttling (address %s).", ip)
        return refuse(LOGIN_BLOCKED, 429)

    user = db.query_one("SELECT user_id, username, password_hash, role, is_active, session_epoch "
                        "FROM app_user WHERE username = %s", (username,))
    if not auth.verify_password(user, password) or not user["is_active"]:
        auth.record_attempt(username, ip, False)
        current_app.logger.info("Failed sign-in (address %s).", ip)
        return refuse(LOGIN_FAILED, 401)

    auth.record_attempt(username, ip, True)
    db.execute("UPDATE app_user SET last_login_at = NOW() WHERE user_id = %s", (user["user_id"],))
    auth.start_session(user)
    return redirect(target)


@bp.route("/logout", methods=["POST"])
def logout():
    auth.end_session()
    flash("You have signed out.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/account/password", methods=["GET", "POST"])
def change_password():
    errors = {}
    if request.method == "POST":
        user = db.query_one("SELECT * FROM app_user WHERE user_id = %s", (g.user["user_id"],))
        current = request.form.get("current_password", "")[:auth.PASSWORD_MAX + 1]
        new = request.form.get("new_password", "")[:auth.PASSWORD_MAX + 1]
        confirm = request.form.get("confirm_password", "")[:auth.PASSWORD_MAX + 1]
        if not auth.verify_password(user, current):
            errors["current_password"] = "Current password is not correct."
        problem = auth.password_problem(new, user["username"])
        if problem:
            errors["new_password"] = problem
        elif new != confirm:
            errors["confirm_password"] = "The two new passwords do not match."
        if not errors:
            # A new epoch signs out every other session of this account.
            db.execute("UPDATE app_user SET password_hash = %s, session_epoch = session_epoch + 1 "
                       "WHERE user_id = %s", (auth.hash_password(new), user["user_id"]))
            user = db.query_one("SELECT * FROM app_user WHERE user_id = %s", (user["user_id"],))
            auth.start_session(user)
            flash("Password changed. Other signed-in sessions have been signed out.", "success")
            return redirect(url_for("dashboard.index"))
    return render_template("auth/password.html", errors=errors), (400 if errors else 200)
