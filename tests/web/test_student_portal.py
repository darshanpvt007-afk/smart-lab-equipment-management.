"""TA80-TA92: student accounts (self-activation), the "My equipment" portal,
borrowing requests and their approval by staff.

Students 1 (Aarav Menon, 24BCE1012) and 2 (Diya Raghavan, 24BEC1045) get
test accounts from the student_accounts fixture; all data is the sample
data in smart_lab_equipment_apptest.
"""
from conftest import TEST_PASSWORD, Client
from test_security import URLS

from app import auth

NEW_PASSWORD = "Student-Test-Pass-31"
GOOD_REQUEST = {"requested_from": "2026-10-12", "requested_until": "2026-10-16",
                "purpose": "Digital electronics lab, experiment 4"}


def text(response):
    return response.get_data(as_text=True)


def session_of(client):
    with client.raw.session_transaction() as sess:
        return dict(sess)


def activate(client, reg, email, password=NEW_PASSWORD, confirm=None):
    return client.post("/activate", {"register_number": reg, "email": email, "password": password,
                                     "confirm_password": confirm or password})


# ---- activation and sign-in ------------------------------------------------------
def test_ta80_student_activates_once_and_is_signed_in(client, anon, sql):
    assert client.post("/users/students/3", {"action": "open"}).status_code == 302      # admin opens it
    response = activate(anon, "25bce1103", "Kabir.Nair@students.example.edu")         # case-insensitive
    assert response.status_code == 302 and response.headers["Location"] == "/my/"
    assert session_of(anon)["sid"] == 3 and "uid" not in session_of(anon)
    row = sql("SELECT password_hash, activated_at, activation_expires_at FROM student_account "
              "WHERE student_id = 3")[0]
    assert row["password_hash"].startswith("scrypt:") and NEW_PASSWORD not in row["password_hash"]
    assert row["activated_at"] is not None and row["activation_expires_at"] is None
    again = activate(Client(anon.raw.application.test_client()), "25BCE1103",
                     "kabir.nair@students.example.edu", "Some-Other-Pass-99")
    assert again.status_code == 400 and "do not match a student account" in text(again)


def test_ta81_activation_refuses_wrong_or_closed_accounts_with_one_message(client, anon, sql):
    client.post("/users/students/3", {"action": "open"})
    client.post("/users/students/5", {"action": "open"})
    sql("UPDATE student_account SET activation_expires_at = NOW() - INTERVAL 1 HOUR WHERE student_id = 5")
    client.post("/users/students/6", {"action": "open"})
    client.post("/users/students/6", {"action": "deactivate"})
    attempts = [("25BCE1103", "someone.else@students.example.edu"),     # wrong e-mail
                ("23BEE1021", "meera.iyer@students.example.edu"),       # activation never opened
                ("25BEC1077", "rohan.kulkarni@students.example.edu"),   # expired
                ("26BCE1150", "sneha.pillai@students.example.edu"),     # deactivated
                ("99XYZ0000", "nobody@students.example.edu")]           # no such student
    for reg, email in attempts:
        response = activate(anon, reg, email)
        assert response.status_code == 400 and "do not match a student account" in text(response), reg
    assert sql("SELECT COUNT(*) AS n FROM student_account WHERE password_hash IS NOT NULL")[0]["n"] == 0
    weak = activate(anon, "25BCE1103", "kabir.nair@students.example.edu", "short")
    assert weak.status_code == 400 and "at least 12" in text(weak)
    mismatch = activate(anon, "25BCE1103", "kabir.nair@students.example.edu", NEW_PASSWORD, "Different-Pass-123")
    assert mismatch.status_code == 400 and "do not match." in text(mismatch)


def test_ta82_students_sign_in_with_their_register_number(app, student_accounts, sql):
    c = Client(app.test_client())
    ok = c.post("/login", {"username": "24bce1012", "password": TEST_PASSWORD})
    assert ok.status_code == 302 and ok.headers["Location"] == "/my/"
    assert session_of(c)["sid"] == 1
    bad = Client(app.test_client()).post("/login", {"username": "24BCE1012", "password": "Wrong-Pass-0000"})
    assert bad.status_code == 401 and "Invalid username or password." in text(bad)
    sql("INSERT INTO student_account (student_id, activation_expires_at) VALUES (3, NOW() + INTERVAL 1 DAY)")
    pending = Client(app.test_client()).post("/login", {"username": "25BCE1103", "password": TEST_PASSWORD})
    assert pending.status_code == 401                                   # not activated yet


def test_ta83_portal_shows_only_the_students_own_records(student_client):
    page = text(student_client("aarav").get("/my/"))
    assert "Aarav Menon" in page and "OSC-DS1-0001" in page and "Overdue 2 days" in page
    for other in ("Diya Raghavan", "Vikram Joshi", "Rohan Kulkarni", "24BEC1045", "@students.example.edu"):
        assert other not in page, other
    assert "11 available now" in page
    diya = text(student_client("diya").get("/my/"))
    assert "Wireless Router" in diya and "Aarav Menon" not in diya and "24BCE1012" not in diya
    assert "Overdue 2 days" not in diya          # Aarav's overdue loan is not shown to Diya
    # Diya's own returned loan of OSC-DS1-0001 (allocation 7, August) is hers to see:
    assert "10 Aug → 17 Aug 2026" in diya


def test_ta84_students_cannot_reach_any_staff_page(student_client, sql):
    c = student_client("aarav")
    for endpoint, (method, url) in URLS.items():
        needed = auth.ENDPOINT_PERMISSIONS[endpoint]
        if needed in (auth.PUBLIC, auth.SIGNED_IN, auth.STUDENT):
            continue
        response = c.get(url) if method == "GET" else c.post(url)
        if endpoint == "dashboard.index":
            assert response.status_code == 302 and response.headers["Location"] == "/my/"
        else:
            assert response.status_code == 403, (endpoint, response.status_code)
    assert sql("SELECT COUNT(*) AS n FROM student")[0]["n"] == 10        # the POSTs changed nothing
    assert "Users" not in text(c.get("/my/"))


# ---- requests --------------------------------------------------------------------
def test_ta85_request_validation(student_client, sql):
    c = student_client("aarav")
    assert c.post("/my/request/5", GOOD_REQUEST).status_code == 302
    row = sql("SELECT student_id, equipment_id, request_status FROM equipment_request")[0]
    assert (row["student_id"], row["equipment_id"], row["request_status"]) == (1, 5, "Pending")
    duplicate = c.post("/my/request/5", GOOD_REQUEST)
    assert duplicate.status_code == 400 and "already have a pending request" in text(duplicate)
    for change, message in ((dict(requested_until="2026-10-11"), "Until must be on or after From."),
                            (dict(requested_from="2026-10-01"), "cannot be before 2026-10-10"),
                            (dict(requested_until="2026-10-31"), "at most 14 days"),
                            (dict(purpose=""), "Purpose is required.")):
        response = c.post("/my/request/6", dict(GOOD_REQUEST, **change))
        assert response.status_code == 400 and message in text(response), message
    unavailable = c.post("/my/request/1", GOOD_REQUEST)               # OSC-DS1-0001 is on loan
    assert unavailable.status_code == 302
    assert c.post("/my/request/6", GOOD_REQUEST).status_code == 302
    assert c.post("/my/request/7", GOOD_REQUEST).status_code == 302
    fourth = c.post("/my/request/11", GOOD_REQUEST)
    assert fourth.status_code == 400 and "already have 3 open requests" in text(fourth)
    assert sql("SELECT COUNT(*) AS n FROM equipment_request")[0]["n"] == 3
    assert c.get("/my/request/999").status_code == 404


def test_ta86_students_can_cancel_only_their_own_pending_requests(student_client, sql):
    aarav, diya = student_client("aarav"), student_client("diya")
    aarav.post("/my/request/5", GOOD_REQUEST)
    rid = sql("SELECT request_id FROM equipment_request")[0]["request_id"]
    assert diya.post(f"/my/requests/{rid}/cancel").status_code == 404
    assert aarav.post(f"/my/requests/{rid}/cancel").status_code == 302
    assert sql("SELECT request_status FROM equipment_request")[0]["request_status"] == "Cancelled"
    aarav.post(f"/my/requests/{rid}/cancel")
    assert "Only a pending request can be cancelled." in text(aarav.get("/my/"))


def test_ta87_staff_approve_issues_the_item_through_the_procedure(student_client, client_as, sql):
    student_client("aarav").post("/my/request/5", GOOD_REQUEST)
    rid = sql("SELECT request_id FROM equipment_request")[0]["request_id"]
    decision = {"staff_id": "1", "expected_return_date": "2026-10-16"}
    assert client_as("technician").post(f"/requests/{rid}/approve", decision).status_code == 403
    staff = client_as("inventory_staff")
    assert "24BCE1012" in text(staff.get("/requests/"))
    response = staff.post(f"/requests/{rid}/approve", decision)
    assert response.status_code == 302
    req = sql("SELECT request_status, allocation_id, decided_by_user_id FROM equipment_request")[0]
    assert req["request_status"] == "Approved" and req["allocation_id"] == 21
    alloc = sql("SELECT equipment_id, student_id, staff_id, allocation_date, expected_return_date, "
                "allocation_status FROM equipment_allocation WHERE allocation_id = 21")[0]
    assert (alloc["equipment_id"], alloc["student_id"], alloc["staff_id"], str(alloc["allocation_date"]),
            str(alloc["expected_return_date"]), alloc["allocation_status"]) == \
        (5, 1, 1, "2026-10-10", "2026-10-16", "Issued")
    assert sql("SELECT availability_status FROM equipment WHERE equipment_id = 5")[0]["availability_status"] \
        == "Allocated"
    again = staff.post(f"/requests/{rid}/approve", decision)
    assert again.status_code == 302 and "already been decided" in text(staff.get("/requests/"))
    assert "DMM-17B-0005" in text(student_client("aarav").get("/my/"))      # now on loan to Aarav


def test_ta88_approval_refused_when_item_is_gone_and_reject_with_note(student_client, client, sql):
    student_client("aarav").post("/my/request/5", GOOD_REQUEST)
    student_client("diya").post("/my/request/5", GOOD_REQUEST)
    first, second = [r["request_id"] for r in sql("SELECT request_id FROM equipment_request ORDER BY request_id")]
    decision = {"staff_id": "1", "expected_return_date": "2026-10-16"}
    assert client.post(f"/requests/{first}/approve", decision).status_code == 302
    client.post(f"/requests/{second}/approve", decision)                       # item already issued
    assert "is Allocated, not Available" in text(client.get("/requests/"))
    assert sql("SELECT request_status FROM equipment_request WHERE request_id = %s",
               (second,))[0]["request_status"] == "Pending"
    assert client.post(f"/requests/{second}/reject", {"decision_note": "Issued to another student"}).status_code == 302
    assert sql("SELECT request_status, decision_note FROM equipment_request WHERE request_id = %s",
               (second,))[0] == {"request_status": "Rejected", "decision_note": "Issued to another student"}
    assert "Issued to another student" in text(student_client("diya").get("/my/"))


# ---- administration ------------------------------------------------------------------
def test_ta89_admin_opens_resets_and_deactivates_student_accounts(app, client, student_client, sql):
    response = client.post("/users/students/enable")
    assert response.status_code == 302
    assert sql("SELECT COUNT(*) AS n FROM student_account")[0]["n"] == 10
    assert sql("SELECT COUNT(*) AS n FROM student_account WHERE password_hash IS NULL "
               "AND activation_expires_at > NOW()")[0]["n"] == 8               # the 8 without accounts
    page = text(client.get("/users/students"))
    assert page.count("Waiting for activation") == 8 and page.count(">Active<") == 2
    aarav = student_client("aarav")
    assert aarav.get("/my/").status_code == 200
    client.post("/users/students/1", {"action": "open"})                         # reset Aarav
    assert aarav.get("/my/").status_code == 302                                  # signed out
    assert sql("SELECT password_hash FROM student_account WHERE student_id = 1")[0]["password_hash"] is None
    client.post("/users/students/2", {"action": "deactivate"})
    c = Client(app.test_client())
    assert c.post("/login", {"username": "24BEC1045", "password": TEST_PASSWORD}).status_code == 401
    assert client.post("/users/students/2", {"action": "explode"}).status_code == 400
    assert client.post("/users/students/999", {"action": "open"}).status_code == 404


def test_ta90_student_sign_in_is_throttled(app, student_accounts):
    c = Client(app.test_client())
    for _ in range(auth.MAX_FAILURES_PER_USER):
        assert c.post("/login", {"username": "24BCE1012", "password": "Wrong-Pass-0000"}).status_code == 401
    assert c.post("/login", {"username": "24BCE1012", "password": TEST_PASSWORD}).status_code == 429


def test_ta91_staff_usernames_cannot_look_like_register_numbers(client, sql):
    response = client.post("/users/new", {"username": "24bce1012", "role": "technician",
                                          "password": NEW_PASSWORD})
    assert response.status_code == 400 and "must not look like a student register number" in text(response)
    assert sql("SELECT COUNT(*) AS n FROM app_user WHERE username = '24bce1012'")[0]["n"] == 0


def test_ta92_student_password_change_signs_out_other_sessions(app, student_accounts, sql):
    phone, laptop = Client(app.test_client()), Client(app.test_client())
    for c in (phone, laptop):
        c.post("/login", {"username": "24BCE1012", "password": TEST_PASSWORD})
    phone.raw.get("/account/password")
    token = session_of(phone)["csrf_token"]
    ok = phone.raw.post("/account/password", data={"csrf_token": token, "current_password": TEST_PASSWORD,
                                                   "new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD})
    assert ok.status_code == 302 and ok.headers["Location"] == "/my/"
    assert phone.get("/my/").status_code == 200 and laptop.get("/my/").status_code == 302
