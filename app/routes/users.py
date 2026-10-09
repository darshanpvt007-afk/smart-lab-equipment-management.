"""Sign-in accounts (administrators only): list, add, change role or
status, reset a password. Accounts are never deleted, only deactivated,
so the history of who could do what stays readable."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .. import auth, db
from . import staff_options, try_db

bp = Blueprint("users", __name__, url_prefix="/users")


def load(user_id):
    user = db.query_one("SELECT * FROM app_user WHERE user_id = %s", (user_id,))
    if user is None:
        abort(404, "Account not found.")
    return user


def staff_id_from_form():
    raw = request.form.get("staff_id", "").strip()
    return int(raw) if raw.isdigit() else None


@bp.route("/")
def list_users():
    rows = db.query_all(
        "SELECT u.user_id, u.username, u.role, u.is_active, u.last_login_at, u.created_at, "
        "       s.staff_name "
        "FROM app_user u LEFT JOIN lab_staff s ON s.staff_id = u.staff_id ORDER BY u.username")
    return render_template("users/list.html", rows=rows)


@bp.route("/new", methods=["GET", "POST"])
def create():
    item, errors = {"role": "inventory_staff"}, {}
    if request.method == "POST":
        item = {"username": request.form.get("username", "").strip().lower(),
                "role": request.form.get("role", ""), "staff_id": staff_id_from_form()}
        password = request.form.get("password", "")[:auth.PASSWORD_MAX + 1]
        errors = auth.validate_new_account(item["username"], item["role"], password)
        if not errors:
            message = try_db(lambda: auth.insert_user(item["username"], item["role"], password,
                                                      item["staff_id"]))
            if message is None:
                flash(f"Account {item['username']} created.", "success")
                return redirect(url_for("users.list_users"))
            errors["username"] = message
    return render_template("users/form.html", item=item, errors=errors, is_new=True,
                           staff=staff_options()), (400 if errors else 200)


@bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
def edit(user_id):
    user = load(user_id)
    errors = {}
    if request.method == "POST":
        role = request.form.get("role", "")
        active = request.form.get("is_active") == "1"
        if role not in auth.ROLES:
            errors["role"] = "Choose a role."
        losing_admin = user["role"] == "admin" and (role != "admin" or not active)
        if user_id == g.user["user_id"] and (role != user["role"] or not active):
            errors["role"] = "You cannot change your own role or deactivate yourself."
        elif losing_admin and auth.active_admin_count(excluding_user_id=user_id) == 0:
            errors["role"] = "At least one active administrator must remain."
        if not errors:
            # Any change of role or status signs the account out everywhere.
            changed = role != user["role"] or active != bool(user["is_active"])
            message = try_db(lambda: db.execute(
                "UPDATE app_user SET role = %s, is_active = %s, staff_id = %s, "
                "session_epoch = session_epoch + %s WHERE user_id = %s",
                (role, active, staff_id_from_form(), 1 if changed else 0, user_id)))
            if message is None:
                flash(f"Account {user['username']} updated.", "success")
                return redirect(url_for("users.list_users"))
            errors["staff_id"] = message
        user = dict(user, role=role, is_active=active, staff_id=staff_id_from_form())
    return render_template("users/form.html", item=user, errors=errors, is_new=False,
                           staff=staff_options()), (400 if errors else 200)


@bp.route("/<int:user_id>/password", methods=["POST"])
def reset_password(user_id):
    user = load(user_id)
    password = request.form.get("password", "")[:auth.PASSWORD_MAX + 1]
    problem = auth.password_problem(password, user["username"])
    if problem:
        flash(problem, "error")
        return redirect(url_for("users.edit", user_id=user_id))
    db.execute("UPDATE app_user SET password_hash = %s, session_epoch = session_epoch + 1 "
               "WHERE user_id = %s", (auth.hash_password(password), user_id))
    flash(f"Password for {user['username']} reset; that account has been signed out everywhere.",
          "success")
    return redirect(url_for("users.list_users"))
