"""Sign-in, roles and permissions.

Access control is enforced on the SERVER for every request:

  * ENDPOINT_PERMISSIONS maps every Flask endpoint to the permission it
    needs. enforce_access() runs before each request and refuses anything
    not listed (fail closed), so a new route is blocked until someone
    decides who may use it. Test TA60 checks that every route is listed.
  * Templates call can('permission') only to HIDE buttons the user may not
    use. Hiding is a convenience, never the protection.

Passwords are stored as salted scrypt hashes (werkzeug.security). The
password itself is never stored, logged or shown.
"""
import secrets
from datetime import timedelta
from urllib.parse import urlsplit

from flask import abort, current_app, g, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from . import db

# ---------------------------------------------------------------------------
# Roles and what each one may do (documented in docs/SECURITY.md)
# ---------------------------------------------------------------------------
ROLES = {
    "admin": "Administrator",
    "lab_manager": "Lab manager",
    "inventory_staff": "Inventory staff",
    "technician": "Technician",
}

PERMISSIONS = {
    # every signed-in user: dashboards, lists, detail pages, search, reports, CSV export
    "view": {"admin", "lab_manager", "inventory_staff", "technician"},
    # issue equipment to students and record returns (sp_allocate / sp_return)
    "issue_return": {"admin", "lab_manager", "inventory_staff"},
    # schedule, start and complete maintenance (sp_start / sp_complete)
    "maintain": {"admin", "lab_manager", "technician"},
    # add and edit equipment items
    "edit_equipment": {"admin", "lab_manager", "inventory_staff"},
    # add and edit students
    "edit_students": {"admin", "lab_manager", "inventory_staff"},
    # labs, categories, suppliers, purchases and lab staff records
    "manage_reference": {"admin", "lab_manager"},
    # deleting any record
    "delete_records": {"admin", "lab_manager"},
    # sign-in accounts
    "manage_users": {"admin"},
}

PUBLIC = "public"          # no sign-in needed
SIGNED_IN = "signed_in"    # any active account, staff or student (own password, sign-out)
STUDENT = "student"        # signed-in STUDENTS only (the "My equipment" portal)

# Students are not a staff role: they never get any permission above. They
# sign in with their register number and only see their own records
# (docs/SECURITY.md section 7).

ENDPOINT_PERMISSIONS = {
    "static": PUBLIC,
    "auth.login": PUBLIC,
    "auth.activate": PUBLIC,
    "health.healthz": PUBLIC,
    "auth.logout": SIGNED_IN,
    "auth.change_password": SIGNED_IN,

    "dashboard.index": "view",
    "dashboard.search": "view",
    "equipment.list_equipment": "view",
    "equipment.detail": "view",
    "equipment.export_csv": "view",
    "students.list_students": "view",
    "students.detail": "view",
    "allocations.list_allocations": "view",
    "maintenance.list_jobs": "view",
    "staff.list_staff": "view",
    "labs.list_labs": "view",
    "categories.list_categories": "view",
    "suppliers.list_suppliers": "view",
    "purchases.list_purchases": "view",
    "reports.index": "view",
    "reports.show": "view",

    "allocations.issue": "issue_return",
    "allocations.return_equipment": "issue_return",

    "maintenance.schedule": "maintain",
    "maintenance.start": "maintain",
    "maintenance.complete": "maintain",

    "equipment.create": "edit_equipment",
    "equipment.edit": "edit_equipment",
    "students.create": "edit_students",
    "students.edit": "edit_students",

    "labs.create": "manage_reference", "labs.edit": "manage_reference",
    "categories.create": "manage_reference", "categories.edit": "manage_reference",
    "suppliers.create": "manage_reference", "suppliers.edit": "manage_reference",
    "staff.create": "manage_reference", "staff.edit": "manage_reference",
    "purchases.create": "manage_reference", "purchases.edit": "manage_reference",

    "equipment.delete": "delete_records", "students.delete": "delete_records",
    "labs.delete": "delete_records", "categories.delete": "delete_records",
    "suppliers.delete": "delete_records", "staff.delete": "delete_records",
    "purchases.delete": "delete_records",

    "users.list_users": "manage_users",
    "users.create": "manage_users",
    "users.edit": "manage_users",
    "users.reset_password": "manage_users",
    "users.student_access": "manage_users",
    "users.enable_students": "manage_users",
    "users.student_account_action": "manage_users",

    "requests.list_requests": "issue_return",
    "requests.approve": "issue_return",
    "requests.reject": "issue_return",

    "portal.home": STUDENT,
    "portal.new_request": STUDENT,
    "portal.cancel_request": STUDENT,
}

# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------
PASSWORD_MIN, PASSWORD_MAX = 12, 128      # the max bounds hashing work per request
USERNAME_RE = r"^[a-z0-9._-]{3,40}$"

# Checked when the username does not exist, so a wrong username takes about
# as long as a wrong password (no timing hint about which accounts exist).
_DUMMY_HASH = generate_password_hash(secrets.token_hex(16))


def hash_password(password):
    return generate_password_hash(password)          # scrypt with a random salt


def password_problem(password, username=""):
    """Return a message if the password is unacceptable, else None."""
    if len(password) < PASSWORD_MIN:
        return f"Password must be at least {PASSWORD_MIN} characters."
    if len(password) > PASSWORD_MAX:
        return f"Password must be at most {PASSWORD_MAX} characters."
    if username and username.lower() in password.lower():
        return "Password must not contain the username."
    if len(set(password)) < 5:
        return "Password is too simple; use a mix of characters."
    return None


def verify_password(user, password):
    if user is None:
        check_password_hash(_DUMMY_HASH, password)
        return False
    return check_password_hash(user["password_hash"], password)


# ---------------------------------------------------------------------------
# Login throttling (brute-force defence), stored in login_attempt
# ---------------------------------------------------------------------------
WINDOW_MINUTES = 15
MAX_FAILURES_PER_USER = 5      # then that username is locked for the rest of the window
MAX_FAILURES_PER_IP = 20       # then that client address is blocked for the window


def client_ip():
    # With TRUST_PROXY=1, ProxyFix has already put the real client address here.
    return (request.remote_addr or "unknown")[:45]


def login_blocked(username, ip):
    """True when recent failures for this username or address exceed the limits."""
    row = db.query_one(
        "SELECT "
        " (SELECT COUNT(*) FROM login_attempt a WHERE a.username = %s AND a.succeeded = 0"
        "   AND a.attempted_at > NOW() - INTERVAL %s MINUTE"
        "   AND a.attempted_at > COALESCE((SELECT MAX(s.attempted_at) FROM login_attempt s"
        "                                  WHERE s.username = %s AND s.succeeded = 1), '1000-01-01')"
        " ) AS user_failures, "
        " (SELECT COUNT(*) FROM login_attempt WHERE client_ip = %s AND succeeded = 0"
        "   AND attempted_at > NOW() - INTERVAL %s MINUTE) AS ip_failures",
        (username, WINDOW_MINUTES, username, ip, WINDOW_MINUTES))
    return row["user_failures"] >= MAX_FAILURES_PER_USER or row["ip_failures"] >= MAX_FAILURES_PER_IP


def record_attempt(username, ip, succeeded):
    db.execute("INSERT INTO login_attempt (username, client_ip, succeeded) VALUES (%s, %s, %s)",
               (username[:40], ip, bool(succeeded)))
    # Keep only one day of attempts: enough for throttling, not a long-term log.
    db.execute("DELETE FROM login_attempt WHERE attempted_at < NOW() - INTERVAL 1 DAY")


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------
def start_session(user):
    """Called after a successful staff login: drop everything in the old
    session (including its CSRF token) and start a fresh one."""
    session.clear()
    session.permanent = True
    session["uid"] = user["user_id"]
    session["epoch"] = user["session_epoch"]
    session["csrf_token"] = secrets.token_hex(16)


def start_student_session(account):
    """Same as start_session, for a student account."""
    session.clear()
    session.permanent = True
    session["sid"] = account["student_id"]
    session["sepoch"] = account["session_epoch"]
    session["csrf_token"] = secrets.token_hex(16)


def end_session():
    session.clear()


def load_user():
    """Put the signed-in, still-active staff account in g.user, or the
    signed-in student in g.student (at most one of them; both None when
    nobody is signed in)."""
    g.user = None
    g.student = None
    if session.get("uid") is not None:
        user = db.query_one(
            "SELECT user_id, username, role, staff_id, is_active, session_epoch "
            "FROM app_user WHERE user_id = %s", (session["uid"],))
        if user is None or not user["is_active"] or user["session_epoch"] != session.get("epoch"):
            end_session()          # deactivated, deleted, or password changed elsewhere
            return
        g.user = user
    elif session.get("sid") is not None:
        student = db.query_one(
            "SELECT a.student_id, a.is_active, a.session_epoch, a.password_hash IS NOT NULL AS activated, "
            "       s.student_name, s.register_number, s.department, s.year_of_study "
            "FROM student_account a JOIN student s ON s.student_id = a.student_id "
            "WHERE a.student_id = %s", (session["sid"],))
        if (student is None or not student["is_active"] or not student["activated"]
                or student["session_epoch"] != session.get("sepoch")):
            end_session()
            return
        g.student = student


def can(permission, user=None):
    user = user if user is not None else g.get("user")
    return bool(user) and user["role"] in PERMISSIONS.get(permission, ())


def safe_next(target):
    """Only allow redirects to a path on this site (no open redirects)."""
    if not target or not target.startswith("/") or target.startswith("//") or "\\" in target:
        return None
    if any(ord(ch) < 32 for ch in target):
        return None
    parts = urlsplit(target)
    if parts.scheme or parts.netloc:
        return None
    return target


def enforce_access():
    """before_request hook: sign-in and permission check for every route."""
    endpoint = request.endpoint
    if endpoint is None:                 # no such URL: let Flask answer 404
        return None
    needed = ENDPOINT_PERMISSIONS.get(endpoint)
    if needed is None:                   # fail closed: unlisted routes are refused
        current_app.logger.error("Route %s has no permission rule; refusing access.", endpoint)
        abort(403)
    if needed == PUBLIC:
        return None
    load_user()
    if g.user is None and g.student is None:
        if request.method == "GET":
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        abort(401)
    if needed == SIGNED_IN:
        return None
    if needed == STUDENT:
        if g.student is None:          # staff never use the student portal
            abort(403)
        return None
    if g.student is not None:          # students never reach staff pages
        if endpoint == "dashboard.index" and request.method == "GET":
            return redirect(url_for("portal.home"))
        abort(403)
    if not can(needed):
        abort(403)
    return None


def init_app(app):
    app.permanent_session_lifetime = timedelta(hours=app.config.get("SESSION_HOURS", 8))
    app.before_request(enforce_access)

    @app.context_processor
    def auth_globals():
        return {"can": can, "current_user": g.get("user"), "current_student": g.get("student"),
                "role_labels": ROLES}


# ---------------------------------------------------------------------------
# Account management (used by the Users pages and the create-user command)
# ---------------------------------------------------------------------------
def validate_new_account(username, role, password, staff_id=None):
    """Return {field: message} for a proposed account (empty when valid)."""
    import re
    errors = {}
    if not re.fullmatch(USERNAME_RE, username or ""):
        errors["username"] = ("Username must be 3-40 characters: lower-case letters, "
                              "digits, dot, dash or underscore.")
    elif looks_like_register_number(username):
        errors["username"] = "Staff usernames must not look like a student register number."
    if role not in ROLES:
        errors["role"] = "Choose a role."
    problem = password_problem(password or "", username or "")
    if problem:
        errors["password"] = problem
    return errors


def insert_user(username, role, password, staff_id=None):
    return db.execute(
        "INSERT INTO app_user (username, password_hash, role, staff_id) VALUES (%s, %s, %s, %s)",
        (username, hash_password(password), role, staff_id))


def active_admin_count(excluding_user_id=None):
    return db.query_one(
        "SELECT COUNT(*) AS n FROM app_user WHERE role = 'admin' AND is_active "
        "AND user_id <> %s", (excluding_user_id or 0,))["n"]


# ---------------------------------------------------------------------------
# Student accounts (self-activation; docs/SECURITY.md section 7)
# ---------------------------------------------------------------------------
ACTIVATION_DAYS = 14


def looks_like_register_number(text):
    import re
    from .validators import REGISTER_RE
    return bool(REGISTER_RE.match((text or "").strip().upper())) and bool(re.fullmatch(r"[0-9A-Za-z]+", text or ""))


def find_student_account(register_number):
    return db.query_one(
        "SELECT a.*, s.register_number, s.email FROM student_account a "
        "JOIN student s ON s.student_id = a.student_id WHERE s.register_number = %s",
        (register_number.strip().upper(),))


def open_activation(student_ids):
    """Allow these students to (re-)activate within ACTIVATION_DAYS. Clears any
    old password and signs the account out everywhere. Returns rows affected."""
    count = 0
    for sid in student_ids:
        count += 1
        db.execute(
            "INSERT INTO student_account (student_id, password_hash, activation_expires_at) "
            "VALUES (%s, NULL, NOW() + INTERVAL %s DAY) "
            "ON DUPLICATE KEY UPDATE password_hash = NULL, is_active = TRUE, activated_at = NULL, "
            "  activation_expires_at = NOW() + INTERVAL %s DAY, session_epoch = session_epoch + 1",
            (sid, ACTIVATION_DAYS, ACTIVATION_DAYS))
    return count
