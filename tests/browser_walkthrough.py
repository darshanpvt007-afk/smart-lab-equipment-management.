"""End-to-end browser walkthrough (TB00-TB15) that also saves screenshots
for the report and the presentation.

It rebuilds the separate database smart_lab_equipment_apptest from the SQL
files, starts the web app on a local port against it, and drives a real
Chromium browser through the main user journeys, checking what appears on
the screen at each step.

Run from the project root (Playwright and Chromium must be installed:
    pip install playwright && python -m playwright install chromium):
    python tests/browser_walkthrough.py
Screenshots are written to docs/screenshots/.
"""
import os
import secrets
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import create_app  # noqa: E402

TEST_DB = "smart_lab_equipment_apptest"
SHOTS = ROOT / "docs" / "screenshots"
BUILD = ["01_create_database.sql", "02_create_tables.sql", "03_insert_sample_data.sql",
         "08_create_views.sql", "11_transaction_procedures.sql", "12_maintenance_procedures.sql",
         "13_app_users.sql"]
# Throw-away passwords for the two walkthrough accounts: random on every run,
# never printed, and the accounts exist only in the test database.
PASSWORDS = {"walk.admin": secrets.token_urlsafe(18), "walk.tech": secrets.token_urlsafe(18)}
PORT = int(os.environ.get("WALKTHROUGH_PORT", "5055"))
BASE = f"http://127.0.0.1:{PORT}"

settings = {
    "host": os.environ.get("DB_HOST", "localhost"), "port": int(os.environ.get("DB_PORT", "3306")),
    "user": os.environ.get("DB_USER", "root"), "password": os.environ.get("DB_PASSWORD", ""),
    "unix_socket": os.environ.get("DB_UNIX_SOCKET", ""),
}


def build_database():
    script = f"DROP DATABASE IF EXISTS {TEST_DB};\n" + "\n".join(
        (ROOT / "sql" / f).read_text(encoding="utf-8").replace("smart_lab_equipment_db", TEST_DB) for f in BUILD)
    with tempfile.NamedTemporaryFile("w", suffix=".cnf", delete=False) as cnf:
        cnf.write(f"[client]\nuser={settings['user']}\npassword={settings['password']}\n")
    args = ["mysql", f"--defaults-extra-file={cnf.name}"]
    args += [f"--socket={settings['unix_socket']}"] if settings["unix_socket"] else \
            [f"--host={settings['host']}", f"--port={settings['port']}"]
    try:
        subprocess.run(args, input=script, text=True, check=True, capture_output=True)
    finally:
        os.unlink(cnf.name)


def start_server():
    app = create_app({"SECRET_KEY": "walkthrough", "DB_NAME": TEST_DB, "REFERENCE_DATE": "2026-10-10",
                      "DB_HOST": settings["host"], "DB_PORT": settings["port"], "DB_USER": settings["user"],
                      "DB_PASSWORD": settings["password"], "DB_UNIX_SOCKET": settings["unix_socket"]})
    from app import auth
    with app.app_context():
        auth.insert_user("walk.admin", "admin", PASSWORDS["walk.admin"], 1)
        auth.insert_user("walk.tech", "technician", PASSWORDS["walk.tech"], 4)
    server = make_server("127.0.0.1", PORT, app)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def sign_in(page, username):
    page.goto(BASE + "/login")
    page.fill("input[name=username]", username)
    page.fill("input[name=password]", PASSWORDS[username])
    page.click("button:has-text('Sign in')")


def main():
    SHOTS.mkdir(parents=True, exist_ok=True)
    build_database()
    server = start_server()
    results = []

    def step(test_id, title, shot, action):
        try:
            action()
            if shot:                                  # None: the step saved its own screenshot
                page.screenshot(path=str(SHOTS / shot), full_page=True)
            results.append((test_id, title, "PASS", ""))
        except Exception as exc:                      # report and continue
            results.append((test_id, title, "FAIL", str(exc).splitlines()[0]))

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        def signin():
            page.goto(BASE + "/equipment/")
            expect(page.locator("h1")).to_have_text("Sign in")               # redirected
            page.screenshot(path=str(SHOTS / "00_sign_in.png"), full_page=True)
            page.fill("input[name=username]", "walk.admin")
            page.fill("input[name=password]", "Wrong-password-123")
            page.click("button:has-text('Sign in')")
            expect(page.locator(".login-error")).to_have_text("Invalid username or password.")
            page.fill("input[name=password]", PASSWORDS["walk.admin"])    # retry on the same page
            page.click("button:has-text('Sign in')")
            expect(page.locator("h1")).to_have_text("Equipment")             # back where we started
        step("TB00", "Sign-in required; wrong password refused; correct one returns to the page",
             "00_signed_in.png", signin)

        def dashboard():
            page.goto(BASE + "/")
            expect(page.locator("h1")).to_have_text("Operations overview")
            expect(page.locator(".kpi-overdue .kpi-n")).to_have_text("3")    # 3 overdue
            expect(page.locator("text=Vikram Joshi")).to_be_visible()
        step("TB01", "Dashboard shows inventory figures and overdue loans", "01_dashboard.png", dashboard)

        def search():
            page.goto(BASE + "/equipment/")
            page.fill("form.filters input[name=q]", "multimeter")
            page.select_option("select[name=status]", "Available")
            page.click("button:has-text('Search')")
            expect(page.locator("text=2 item(s) found.")).to_be_visible()
        step("TB02", "Equipment search by name and availability", "02_equipment_search.png", search)

        def detail():
            page.goto(BASE + "/equipment/1")
            expect(page.locator("h1")).to_contain_text("OSC-DS1-0001")
            expect(page.locator("text=Faulty power switch replaced")).to_be_visible()
        step("TB03", "Equipment detail with allocation and maintenance history", "03_equipment_detail.png", detail)

        def issue_invalid():
            page.goto(BASE + "/allocations/new")
            page.select_option("select[name=equipment_id]", "15")
            page.select_option("select[name=student_id]", "10")
            page.select_option("select[name=staff_id]", "1")
            page.fill("input[name=expected_return_date]", "2026-10-01")
            page.click("button:has-text('Issue')")
            expect(page.locator(".error")).to_have_text(
                "Expected return date must be on or after the allocation date.")
            expect(page.locator("[data-check=dates]")).to_have_class("check-bad")   # live check agrees
        step("TB04", "Issue form rejects a due date before the issue date", "04_issue_validation.png", issue_invalid)

        def issue_ok():
            page.fill("input[name=expected_return_date]", "2026-10-17")
            page.click("button:has-text('Issue')")
            expect(page.locator(".flash-success")).to_have_text("Equipment issued (allocation #21).")
        step("TB05", "Equipment issued through sp_allocate_equipment", "05_issue_success.png", issue_ok)

        def return_item():
            page.goto(BASE + "/allocations/17/return")
            page.select_option("select[name=return_condition]", "Good")
            page.fill("textarea[name=remarks]", "Returned with probes")
            page.screenshot(path=str(SHOTS / "06_return_form.png"), full_page=True)
            page.click("button:has-text('Record return')")
            expect(page.locator(".flash-success")).to_contain_text("Return of OSC-DS1-0001 recorded.")
        step("TB06", "Return recorded through sp_return_equipment", "07_after_return.png", return_item)

        def duplicate():
            page.goto(BASE + "/students/new")
            page.fill("input[name=student_name]", "Copy Student")
            page.fill("input[name=register_number]", "24BCE1012")
            page.fill("input[name=department]", "CSE")
            page.fill("input[name=year_of_study]", "2")
            page.fill("input[name=email]", "copy@students.example.edu")
            page.click("button:has-text('Save')")
            expect(page.locator(".flash-error")).to_have_text("A student with this register number already exists.")
        step("TB07", "Duplicate register number shows a friendly error", "08_duplicate_student.png", duplicate)

        def maintenance():
            page.goto(BASE + "/maintenance/?status=Scheduled")
            page.locator("tr:has-text('MCU-ARD-0009') button:has-text('Start')").click()
            expect(page.locator(".flash-success")).to_contain_text("now Under Maintenance")
            page.goto(BASE + "/maintenance/")
        step("TB08", "Maintenance job started; list shows all jobs", "09_maintenance.png", maintenance)

        def report():
            page.goto(BASE + "/reports/frequent-borrowers")
            expect(page.locator("pre.sql")).to_contain_text("HAVING COUNT(*) >")
            expect(page.locator("text=4 row(s).")).to_be_visible()
        step("TB09", "Report page shows the SQL and its result", "10_report_sql.png", report)

        def student():
            page.goto(BASE + "/students/1")
            expect(page.locator("h1")).to_contain_text("Aarav Menon")
            expect(page.locator("tbody tr")).to_have_count(4)
        step("TB10", "Student detail with allocation history", "11_student_detail.png", student)

        def saved_views():
            page.goto(BASE + "/equipment/")
            page.click(".tabs a:has-text('Needs attention')")
            count = page.locator(".tabs a.active .tab-count").inner_text()
            expect(page.locator("table.data tbody tr")).to_have_count(int(count))
            page.click("th a:has-text('Last activity')")
            expect(page.locator("th[aria-sort=ascending]")).to_contain_text("Last activity")
        step("TB11", "Saved view tab and sortable column on the equipment list", "12_equipment_views.png", saved_views)

        def issue_form_helpers():
            page.goto(BASE + "/allocations/new?equipment_id=5")
            page.select_option("select[name=student_id]", "10")
            page.click("button.chip:has-text('2 weeks')")
            expect(page.locator("input[name=expected_return_date]")).to_have_value("2026-10-24")
            expect(page.locator("#checks li.check-ok")).to_have_count(4)
            expect(page.locator("#sum-item")).to_have_text("DMM-17B-0005")
        step("TB12", "Issue form: quick due date, pre-issue checks and summary", "13_issue_form.png", issue_form_helpers)

        def mobile():
            page.set_viewport_size({"width": 390, "height": 844})
            page.goto(BASE + "/")
            expect(page.locator("#sidebar")).not_to_be_in_viewport()
            page.click(".nav-toggle")
            expect(page.locator("#sidebar")).to_be_in_viewport()
            page.wait_for_timeout(300)                 # let the slide-in finish before the screenshot
            overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            assert overflow <= 0, f"page scrolls sideways by {overflow}px"
        step("TB13", "Phone width: menu opens from the toggle, no sideways scroll", "14_mobile_menu.png", mobile)

        def technician():
            page.set_viewport_size({"width": 1440, "height": 900})
            tech = browser.new_page(viewport={"width": 1440, "height": 900})
            try:
                sign_in(tech, "walk.tech")
                expect(tech.locator("h1")).to_have_text("Operations overview")
                expect(tech.locator("nav.sidebar >> text=Issue equipment")).to_have_count(0)
                tech.goto(BASE + "/allocations/new")
                expect(tech.locator("h1")).to_have_text("Error 403")
                tech.goto(BASE + "/maintenance/")
                expect(tech.locator("button:has-text('Start')").first).to_be_visible()
                tech.screenshot(path=str(SHOTS / "15_technician_role.png"), full_page=True)
            finally:
                tech.close()
        step("TB14", "Technician role: no issue action, server refuses it, maintenance allowed",
             None, technician)

        def logout():
            page.set_viewport_size({"width": 1440, "height": 900})
            page.goto(BASE + "/")
            page.click("details.user-menu summary")
            page.click("button:has-text('Sign out')")
            expect(page.locator(".flash-success")).to_have_text("You have signed out.")
            page.goto(BASE + "/")
            expect(page.locator("h1")).to_have_text("Sign in")
        step("TB15", "Sign out ends the session", "16_signed_out.png", logout)


        browser.close()
    server.shutdown()

    for test_id, title, status, detail in results:
        print(f"{status}  {test_id}  {title}" + (f"\n      {detail}" if detail else ""))
    failed = sum(r[2] == "FAIL" for r in results)
    print(f"Passed: {len(results) - failed}   Failed: {failed}   Total: {len(results)}")
    print(f"Screenshots: {SHOTS}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
