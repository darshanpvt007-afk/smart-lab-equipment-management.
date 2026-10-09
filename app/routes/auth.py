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
    if g.student is not None:
        return redirect(url_for("portal.home"))
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

    if auth.looks_like_register_number(username):
        # Students sign in with their register number (staff usernames never look like one).
        account = auth.find_student_account(username)
        usable = account is not None and account["password_hash"] is not None and account["is_active"]
        if not auth.verify_password(account if usable else None, password):
            auth.record_attempt(username, ip, False)
            current_app.logger.info("Failed student sign-in (address %s).", ip)
            return refuse(LOGIN_FAILED, 401)
        auth.record_attempt(username, ip, True)
        db.execute("UPDATE student_account SET last_login_at = NOW() WHERE student_id = %s",
                   (account["student_id"],))
        auth.start_student_session(account)
        return redirect(url_for("portal.home"))

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


ACTIVATION_FAILED = ("These details do not match a student account that is waiting to be "
                     "activated. Check your register number and the e-mail address the lab has "
                     "for you, or ask the lab administrator to open activation again.")


@bp.route("/activate", methods=["GET", "POST"])
def activate():
    """One-time student activation: register number + e-mail on record, then
    the student chooses a password. Only works while an administrator has
    opened activation for that student (and before it expires)."""
    errors, item = {}, {}
    if request.method == "POST":
        item = {"register_number": request.form.get("register_number", "").strip().upper()[:15],
                "email": request.form.get("email", "").strip().lower()[:120]}
        password = request.form.get("password", "")[:auth.PASSWORD_MAX + 1]
        confirm = request.form.get("confirm_password", "")[:auth.PASSWORD_MAX + 1]
        ip = auth.client_ip()
        key = "activate:" + item["register_number"].lower()
        if auth.login_blocked(key, ip):
            errors["form"] = LOGIN_BLOCKED
            return render_template("auth/activate.html", item=item, errors=errors), 429
        account = auth.find_student_account(item["register_number"]) if item["register_number"] else None
        pending = (account is not None and account["password_hash"] is None and account["is_active"]
                   and account["email"].lower() == item["email"]
                   and db.query_one("SELECT activation_expires_at > NOW() AS ok FROM student_account "
                                    "WHERE student_id = %s", (account["student_id"],))["ok"])
        if not pending:
            auth.record_attempt(key, ip, False)
            errors["form"] = ACTIVATION_FAILED
        else:
            problem = auth.password_problem(password, item["register_number"])
            if problem:
                errors["password"] = problem
            elif password != confirm:
                errors["confirm_password"] = "The two passwords do not match."
        if not errors:
            db.execute("UPDATE student_account SET password_hash = %s, activated_at = NOW(), "
                       "activation_expires_at = NULL, session_epoch = session_epoch + 1 "
                       "WHERE student_id = %s AND password_hash IS NULL",
                       (auth.hash_password(password), account["student_id"]))
            account = auth.find_student_account(item["register_number"])
            if not auth.verify_password(account, password):
                # Someone else activated this account at the same moment: refuse.
                auth.record_attempt(key, ip, False)
                errors["form"] = ACTIVATION_FAILED
                return render_template("auth/activate.html", item=item, errors=errors), 400
            auth.record_attempt(key, ip, True)
            auth.start_student_session(account)
            flash("Your account is active. Sign in next time with your register number.", "success")
            return redirect(url_for("portal.home"))
    return render_template("auth/activate.html", item=item, errors=errors), (400 if errors else 200)


@bp.route("/logout", methods=["POST"])
def logout():
    auth.end_session()
    flash("You have signed out.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/account/password", methods=["GET", "POST"])
def change_password():
    errors = {}
    if g.student is not None:
        return change_student_password()
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


def change_student_password():
    errors = {}
    if request.method == "POST":
        account = db.query_one("SELECT * FROM student_account WHERE student_id = %s",
                               (g.student["student_id"],))
        current = request.form.get("current_password", "")[:auth.PASSWORD_MAX + 1]
        new = request.form.get("new_password", "")[:auth.PASSWORD_MAX + 1]
        confirm = request.form.get("confirm_password", "")[:auth.PASSWORD_MAX + 1]
        if not auth.verify_password(account, current):
            errors["current_password"] = "Current password is not correct."
        problem = auth.password_problem(new, g.student["register_number"])
        if problem:
            errors["new_password"] = problem
        elif new != confirm:
            errors["confirm_password"] = "The two new passwords do not match."
        if not errors:
            db.execute("UPDATE student_account SET password_hash = %s, session_epoch = session_epoch + 1 "
                       "WHERE student_id = %s", (auth.hash_password(new), account["student_id"]))
            account = db.query_one("SELECT * FROM student_account WHERE student_id = %s",
                                   (account["student_id"],))
            auth.start_student_session(account)
            flash("Password changed. Other signed-in sessions have been signed out.", "success")
            return redirect(url_for("portal.home"))
    return render_template("auth/password.html", errors=errors), (400 if errors else 200)
