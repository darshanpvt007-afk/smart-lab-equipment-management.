"""TA50-TA72: sign-in, sessions, roles, CSRF, throttling, headers,
configuration safety, health check, account management and migration safety.

Everything runs against smart_lab_equipment_apptest (see conftest.py) with
fake test accounts; no real credentials are used or printed.
"""
import re
import subprocess

import pytest
from werkzeug.security import check_password_hash

from app import ConfigError, auth, create_app

from conftest import BUILD_FILES, DEV_DB, ROOT, TEST_DB, TEST_PASSWORD, Client

GOOD_NEW_PASSWORD = "Another-Test-Pass-77"


def text(response):
    return response.get_data(as_text=True)


def login(client, username, password=TEST_PASSWORD, next_url=""):
    return client.post("/login", {"username": username, "password": password, "next": next_url})


def session_of(client):
    with client.raw.session_transaction() as sess:
        return dict(sess)


# ---- sign-in / sign-out ------------------------------------------------------
def test_ta50_login_success_starts_a_fresh_session(anon, accounts, sql):
    before = session_of(anon)["csrf_token"]
    response = login(anon, "inventory.staff", next_url="/equipment/")
    assert response.status_code == 302 and response.headers["Location"] == "/equipment/"
    after = session_of(anon)
    assert after["uid"] == accounts["inventory_staff"]
    assert after["csrf_token"] != before                     # session renewed at login
    assert sql("SELECT last_login_at FROM app_user WHERE user_id = %s",
               (accounts["inventory_staff"],))[0]["last_login_at"] is not None
    cookie = response.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie
    assert TEST_PASSWORD not in cookie


def test_ta51_wrong_password_and_unknown_user_look_the_same(anon, accounts):
    wrong = login(anon, "admin", "Not-The-Right-Password-1")
    unknown = login(anon, "nobody.here", "Not-The-Right-Password-1")
    assert wrong.status_code == unknown.status_code == 401
    assert "Invalid username or password." in text(wrong)
    assert "Invalid username or password." in text(unknown)
    assert "uid" not in session_of(anon)


def test_ta52_logout_is_post_only_and_clears_the_session(client):
    assert client.get("/logout").status_code == 405
    assert client.raw.post("/logout", data={}).status_code == 400          # no CSRF token
    assert "uid" in session_of(client)
    response = client.post("/logout")
    assert response.status_code == 302 and response.headers["Location"] == "/login"
    assert session_of(client) == {"_flashes": [("success", "You have signed out.")]}
    assert client.get("/").status_code == 302                                # signed out


def test_ta53_unauthenticated_requests_are_refused(app, anon):
    for rule in app.url_map.iter_rules():
        if auth.ENDPOINT_PERMISSIONS[rule.endpoint] == auth.PUBLIC:
            continue
        url = URLS[rule.endpoint][1]
        if "GET" in rule.methods:
            response = anon.get(url)
            assert response.status_code == 302, url
            assert response.headers["Location"].startswith("/login?next="), url
        else:
            assert anon.post(url).status_code == 401, url


def test_ta54_login_page_is_csrf_protected(anon, accounts):
    anon.get("/login")
    response = anon.raw.post("/login", data={"username": "admin", "password": TEST_PASSWORD})
    assert response.status_code == 400
    assert "uid" not in session_of(anon)


# ---- authorization -----------------------------------------------------------
# Sample URL for every endpoint: (method, url). Ids exist in the sample data.
URLS = {
    "static": ("GET", "/static/style.css"),
    "auth.login": ("GET", "/login"), "auth.logout": ("POST", "/logout"),
    "auth.change_password": ("GET", "/account/password"),
    "health.healthz": ("GET", "/healthz"),
    "dashboard.index": ("GET", "/"), "dashboard.search": ("GET", "/search?q=a"),
    "equipment.list_equipment": ("GET", "/equipment/"), "equipment.detail": ("GET", "/equipment/1"),
    "equipment.export_csv": ("GET", "/equipment/export.csv"),
    "equipment.create": ("GET", "/equipment/new"), "equipment.edit": ("GET", "/equipment/1/edit"),
    "equipment.delete": ("POST", "/equipment/20/delete"),
    "students.list_students": ("GET", "/students/"), "students.detail": ("GET", "/students/1"),
    "students.create": ("GET", "/students/new"), "students.edit": ("GET", "/students/1/edit"),
    "students.delete": ("POST", "/students/10/delete"),
    "allocations.list_allocations": ("GET", "/allocations/"),
    "allocations.issue": ("GET", "/allocations/new"),
    "allocations.return_equipment": ("GET", "/allocations/17/return"),
    "maintenance.list_jobs": ("GET", "/maintenance/"), "maintenance.schedule": ("GET", "/maintenance/new"),
    "maintenance.start": ("POST", "/maintenance/10/start"),
    "maintenance.complete": ("GET", "/maintenance/8/complete"),
    "staff.list_staff": ("GET", "/staff/"), "staff.create": ("GET", "/staff/new"),
    "staff.edit": ("GET", "/staff/1/edit"), "staff.delete": ("POST", "/staff/4/delete"),
    "labs.list_labs": ("GET", "/labs/"), "labs.create": ("GET", "/labs/new"),
    "labs.edit": ("GET", "/labs/1/edit"), "labs.delete": ("POST", "/labs/1/delete"),
    "categories.list_categories": ("GET", "/categories/"), "categories.create": ("GET", "/categories/new"),
    "categories.edit": ("GET", "/categories/1/edit"), "categories.delete": ("POST", "/categories/1/delete"),
    "suppliers.list_suppliers": ("GET", "/suppliers/"), "suppliers.create": ("GET", "/suppliers/new"),
    "suppliers.edit": ("GET", "/suppliers/1/edit"), "suppliers.delete": ("POST", "/suppliers/1/delete"),
    "purchases.list_purchases": ("GET", "/purchases/"), "purchases.create": ("GET", "/purchases/new"),
    "purchases.edit": ("GET", "/purchases/1/edit"), "purchases.delete": ("POST", "/purchases/1/delete"),
    "reports.index": ("GET", "/reports/"), "reports.show": ("GET", "/reports/overdue"),
    "users.list_users": ("GET", "/users/"), "users.create": ("GET", "/users/new"),
    "users.edit": ("GET", "/users/1/edit"), "users.reset_password": ("POST", "/users/2/password"),
    "users.student_access": ("GET", "/users/students"),
    "users.enable_students": ("POST", "/users/students/enable"),
    "users.student_account_action": ("POST", "/users/students/3"),
    "requests.list_requests": ("GET", "/requests/"),
    "requests.approve": ("POST", "/requests/1/approve"), "requests.reject": ("POST", "/requests/1/reject"),
    "auth.activate": ("GET", "/activate"),
    "portal.home": ("GET", "/my/"), "portal.new_request": ("GET", "/my/request/5"),
    "portal.cancel_request": ("POST", "/my/requests/1/cancel"),
}

ALL = {"admin", "lab_manager", "inventory_staff", "technician"}
# The documented policy (docs/SECURITY.md), written out independently of app/auth.py.
EXPECTED = {
    "view": ALL,
    "issue_return": {"admin", "lab_manager", "inventory_staff"},
    "maintain": {"admin", "lab_manager", "technician"},
    "edit_equipment": {"admin", "lab_manager", "inventory_staff"},
    "edit_students": {"admin", "lab_manager", "inventory_staff"},
    "manage_reference": {"admin", "lab_manager"},
    "delete_records": {"admin", "lab_manager"},
    "manage_users": {"admin"},
    auth.SIGNED_IN: ALL,
    auth.PUBLIC: ALL,
    auth.STUDENT: set(),             # staff never use the student portal
}


def test_ta55_every_route_has_a_rule_and_a_sample_url(app):
    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
    assert endpoints == set(auth.ENDPOINT_PERMISSIONS) == set(URLS)
    assert {k: v for k, v in auth.PERMISSIONS.items()} == {k: v for k, v in EXPECTED.items()
                                                          if k not in (auth.PUBLIC, auth.SIGNED_IN, auth.STUDENT)}


@pytest.mark.parametrize("role", sorted(ALL))
def test_ta56_role_matrix_is_enforced_by_the_server(client_as, role):
    c = client_as(role)
    for endpoint, (method, url) in URLS.items():
        if endpoint == "auth.logout":
            continue                                    # would end this client's session
        permission = auth.ENDPOINT_PERMISSIONS[endpoint]
        response = c.get(url) if method == "GET" else c.post(url)
        if role in EXPECTED[permission]:
            assert response.status_code not in (401, 403), (role, endpoint, response.status_code)
        else:
            assert response.status_code == 403, (role, endpoint, response.status_code)


def test_ta57_denied_actions_change_nothing(client_as, sql):
    tech = client_as("technician")
    assert tech.post("/students/10/delete").status_code == 403
    assert tech.post("/allocations/new", {"equipment_id": "15", "student_id": "10", "staff_id": "1",
                                         "allocation_date": "2026-10-10",
                                         "expected_return_date": "2026-10-17"}).status_code == 403
    staff = client_as("inventory_staff")
    assert staff.post("/maintenance/10/start").status_code == 403
    assert staff.post("/labs/new", {"lab_name": "X", "location": "Y", "capacity": "5",
                                    "lab_type": "Z"}).status_code == 403
    assert sql("SELECT COUNT(*) AS n FROM student")[0]["n"] == 10
    assert sql("SELECT COUNT(*) AS n FROM equipment_allocation")[0]["n"] == 20
    assert sql("SELECT maintenance_status FROM maintenance WHERE maintenance_id = 10")[0][
        "maintenance_status"] == "Scheduled"
    assert sql("SELECT COUNT(*) AS n FROM lab")[0]["n"] == 4


def test_ta58_unlisted_routes_fail_closed(app, client):
    @app.route("/forgotten-route")
    def forgotten():
        return "should never be reachable"
    assert client.get("/forgotten-route").status_code == 403


def test_ta59_interface_hides_actions_the_role_cannot_use(client_as):
    tech = text(client_as("technician").get("/equipment/1"))
    assert "Record return" not in tech and "Edit details" not in tech and ">Delete<" not in tech
    assert "Schedule maintenance" in tech
    staff = text(client_as("inventory_staff").get("/labs/"))
    assert "+ Add laboratory" not in staff and ">Edit<" not in staff and ">Delete<" not in staff
    assert ">Users<" not in text(client_as("lab_manager").get("/"))
    assert ">Users<" in text(client_as("admin").get("/"))


# ---- CSRF and sessions -----------------------------------------------------------
def test_ta60_state_changing_requests_need_the_csrf_token(client, sql):
    data = {"lab_name": "CSRF Lab", "location": "Nowhere", "capacity": "5", "lab_type": "Test"}
    assert client.raw.post("/labs/new", data=data).status_code == 400                   # missing
    assert client.raw.post("/labs/new", data=dict(data, csrf_token="forged")).status_code == 400
    assert sql("SELECT COUNT(*) AS n FROM lab WHERE lab_name = 'CSRF Lab'")[0]["n"] == 0


def test_ta61_password_change_signs_out_other_sessions(app, accounts, sql):

    phone, laptop = Client(app.test_client()), Client(app.test_client())
    login(phone, "technician"), login(laptop, "technician")
    phone.raw.get("/account/password")
    token = session_of(phone)["csrf_token"]
    bad = phone.raw.post("/account/password", data={"csrf_token": token, "current_password": "wrong-one-123",
                                                    "new_password": GOOD_NEW_PASSWORD,
                                                    "confirm_password": GOOD_NEW_PASSWORD})
    assert bad.status_code == 400 and "Current password is not correct." in text(bad)
    ok = phone.raw.post("/account/password", data={"csrf_token": token, "current_password": TEST_PASSWORD,
                                                   "new_password": GOOD_NEW_PASSWORD,
                                                   "confirm_password": GOOD_NEW_PASSWORD})
    assert ok.status_code == 302
    assert phone.get("/").status_code == 200              # this session continues
    assert laptop.get("/").status_code == 302             # the other one is signed out
    stored = sql("SELECT password_hash FROM app_user WHERE username = 'technician'")[0]["password_hash"]
    assert check_password_hash(stored, GOOD_NEW_PASSWORD) and GOOD_NEW_PASSWORD not in stored


def test_ta62_deactivated_accounts_are_signed_out_and_cannot_sign_in(client, client_as, accounts, anon):
    manager = client_as("lab_manager")
    assert manager.get("/").status_code == 200
    response = client.post(f"/users/{accounts['lab_manager']}/edit", {"role": "lab_manager"})  # no is_active
    assert response.status_code == 302
    assert manager.get("/").status_code == 302
    assert login(anon, "lab.manager").status_code == 401


def test_ta63_session_cookie_settings(app, monkeypatch):
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    prod = production_app(monkeypatch)
    assert prod.config["SESSION_COOKIE_SECURE"] is True
    assert prod.permanent_session_lifetime.total_seconds() == 8 * 3600


# ---- brute force and redirects --------------------------------------------------
def test_ta64_repeated_failures_lock_the_username(anon, accounts, sql):
    for _ in range(auth.MAX_FAILURES_PER_USER):
        assert login(anon, "admin", "Wrong-Password-000").status_code == 401
    blocked = login(anon, "admin")                        # correct password, still refused
    assert blocked.status_code == 429 and "Too many failed sign-in attempts" in text(blocked)
    assert "uid" not in session_of(anon)
    assert login(anon, "technician").status_code == 302   # other accounts are not locked


def test_ta65_repeated_failures_block_the_client_address(anon, accounts):
    for i in range(auth.MAX_FAILURES_PER_IP):
        login(anon, f"guess{i:02d}", "Wrong-Password-000")
    assert login(anon, "technician").status_code == 429


def test_ta66_old_attempts_expire_and_success_resets_the_username_count(app, accounts, sql):
    fresh = lambda: Client(app.test_client())     # noqa: E731 - a new browser for each sign-in
    browser = fresh()
    for _ in range(auth.MAX_FAILURES_PER_USER - 1):
        login(browser, "admin", "Wrong-Password-000")
    assert login(browser, "admin").status_code == 302
    browser = fresh()
    for _ in range(auth.MAX_FAILURES_PER_USER - 1):
        login(browser, "admin", "Wrong-Password-000")
    assert login(browser, "admin").status_code == 302     # count restarted after the success
    sql("UPDATE login_attempt SET attempted_at = NOW() - INTERVAL 2 DAY")
    login(fresh(), "admin", "Wrong-Password-000")          # writing an attempt prunes old rows
    assert sql("SELECT COUNT(*) AS n FROM login_attempt")[0]["n"] == 1


@pytest.mark.parametrize("target", ["//evil.example/", "https://evil.example/", "/\\evil.example",
                                    "javascript:alert(1)", "/%0d%0aSet-Cookie:x"])
def test_ta67_login_never_redirects_off_site(anon, accounts, target):
    response = login(anon, "admin", next_url=target)
    assert response.status_code == 302
    location = response.headers["Location"]
    assert location in ("/", target) and not location.startswith("//") and "evil" not in location


# ---- passwords and accounts -------------------------------------------------------
def test_ta68_passwords_are_salted_hashes_with_a_policy(client, sql):
    for name in ("first.user", "second.user"):
        assert client.post("/users/new", {"username": name, "role": "technician",
                                          "password": GOOD_NEW_PASSWORD}).status_code == 302
    rows = sql("SELECT password_hash FROM app_user WHERE username IN ('first.user', 'second.user')")
    hashes = [r["password_hash"] for r in rows]
    assert all(h.startswith("scrypt:") and GOOD_NEW_PASSWORD not in h for h in hashes)
    assert hashes[0] != hashes[1]                                  # different salts
    for weak, message in (("short", "at least 12"), ("aaaaaaaaaaaaaaaa", "too simple"),
                          ("weak.user-password", "must not contain the username")):
        response = client.post("/users/new", {"username": "weak.user", "role": "technician",
                                              "password": weak})
        assert response.status_code == 400 and message in text(response)
    assert sql("SELECT COUNT(*) AS n FROM app_user WHERE username = 'weak.user'")[0]["n"] == 0


def test_ta69_admins_cannot_lock_themselves_out(client, accounts, sql):
    me = accounts["admin"]
    response = client.post(f"/users/{me}/edit", {"role": "technician", "is_active": "1"})
    assert response.status_code == 400 and "cannot change your own role" in text(response)
    assert sql("SELECT role FROM app_user WHERE user_id = %s", (me,))[0]["role"] == "admin"


def test_ta69b_account_form_errors_are_friendly(client, accounts):
    duplicate = client.post("/users/new", {"username": "technician", "role": "technician",
                                           "password": GOOD_NEW_PASSWORD})
    assert duplicate.status_code == 400 and "An account with this username already exists." in text(duplicate)
    bad_link = client.post(f"/users/{accounts['technician']}/edit",
                           {"role": "technician", "is_active": "1", "staff_id": "999"})
    assert bad_link.status_code == 400 and "does not exist" in text(bad_link)


def test_ta70_create_user_command(app, sql):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["create-user", "--username", "First.Admin", "--role", "admin",
                                 "--password-stdin"], input=GOOD_NEW_PASSWORD + "\n")
    assert result.exit_code == 0, result.output
    assert "Created account first.admin with role admin." in result.output
    assert GOOD_NEW_PASSWORD not in result.output
    again = runner.invoke(args=["create-user", "--username", "first.admin", "--role", "admin",
                                "--password-stdin"], input=GOOD_NEW_PASSWORD + "\n")
    assert again.exit_code != 0 and "already exists" in again.output
    weak = runner.invoke(args=["create-user", "--username", "weak.admin", "--role", "admin",
                               "--password-stdin"], input="short\n")
    assert weak.exit_code != 0 and "at least 12" in weak.output
    assert sql("SELECT COUNT(*) AS n FROM app_user WHERE username LIKE %s", ("%.admin",))[0]["n"] == 1


# ---- configuration, headers, errors, health ------------------------------------------
def production_app(monkeypatch, **overrides):
    env = {"APP_ENV": "production", "SECRET_KEY": "s" * 40, "DB_USER": "smartlab_app",
           "DB_PASSWORD": "placeholder-not-real"}
    env.update(overrides)
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    return create_app()


@pytest.mark.parametrize("overrides, problem", [
    ({"SECRET_KEY": None}, "SECRET_KEY"), ({"SECRET_KEY": "too-short"}, "SECRET_KEY"),
    ({"DB_USER": "root"}, "DB_USER"), ({"DB_PASSWORD": None}, "DB_PASSWORD"),
    ({"COOKIE_SECURE": "0"}, "COOKIE_SECURE")])
def test_ta71_production_refuses_unsafe_configuration(monkeypatch, overrides, problem):
    with pytest.raises(ConfigError) as caught:
        production_app(monkeypatch, **overrides)
    assert problem in str(caught.value)
    assert "placeholder-not-real" not in str(caught.value) and "s" * 40 not in str(caught.value)


def test_ta72_headers_errors_size_limit_and_health(app, client, anon):
    page = client.get("/")
    csp = page.headers["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp and "unsafe-inline" not in \
        csp.split("script-src")[1].split(";")[0]
    assert page.headers["X-Content-Type-Options"] == "nosniff"
    assert page.headers["X-Frame-Options"] == "DENY"
    assert page.headers["Cache-Control"] == "no-store"
    assert not re.search(r"\son[a-z]+=", text(page))                  # no inline event handlers
    assert client.post("/labs/new", {"lab_name": "x" * 70000}).status_code == 413
    health = anon.get("/healthz")
    assert health.status_code == 200 and health.get_json() == {"status": "ok"}
    app.config["DB_NAME"] = "no_such_database_xyz"
    app.config["PROPAGATE_EXCEPTIONS"] = False          # show the real 500 page, as in production
    down = anon.get("/healthz")
    assert down.status_code == 503 and down.get_json() == {"status": "unavailable"}
    broken = client.get("/")                                           # a real error page
    assert broken.status_code == 500
    body = text(broken)
    assert "no_such_database_xyz" not in body and "Traceback" not in body and "mysql" not in body.lower()


# ---- migration and test-database safety ----------------------------------------------
@pytest.mark.parametrize("migration_file", ["13_app_users.sql", "15_student_portal.sql"])
def test_ta73_migrations_are_additive_and_safe_to_rerun(mysql_cli_args, sql, accounts, migration_file):
    sql("INSERT INTO student_account (student_id, activation_expires_at) VALUES (1, NOW() + INTERVAL 1 DAY)")
    tables = ("student", "equipment", "equipment_allocation", "maintenance", "app_user", "student_account")
    before = {t: sql(f"SELECT COUNT(*) AS n FROM {t}")[0]["n"] for t in tables}
    migration = (ROOT / "sql" / migration_file).read_text(encoding="utf-8")
    statements = [line for line in migration.splitlines() if not line.lstrip().startswith("--")]
    assert not re.search(r"^\s*(DROP|TRUNCATE|DELETE|UPDATE|ALTER|INSERT|REPLACE)\b",
                         "\n".join(statements), re.I | re.M)
    for _ in range(2):
        result = subprocess.run(mysql_cli_args, input=migration.replace(DEV_DB, TEST_DB),
                                text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
    after = {t: sql(f"SELECT COUNT(*) AS n FROM {t}")[0]["n"] for t in before}
    assert after == before and before["app_user"] == 4 and before["student_account"] == 1


def test_ta74_tests_cannot_touch_the_development_database():
    assert TEST_DB != DEV_DB and TEST_DB.endswith("_apptest")
    assert "13_app_users.sql" in BUILD_FILES and "15_student_portal.sql" in BUILD_FILES
    walkthrough = (ROOT / "tests" / "browser_walkthrough.py").read_text(encoding="utf-8")
    assert 'TEST_DB = "smart_lab_equipment_apptest"' in walkthrough
