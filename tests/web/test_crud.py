"""TA07-TA19: create, read, update and delete through the web forms,
including input validation and friendly database error messages."""

STUDENT = {"student_name": "Rahul Verma", "register_number": "26bce1201", "department": "cse",
           "year_of_study": "1", "email": "rahul.verma@students.example.edu"}


def text(response):
    return response.get_data(as_text=True)


# ---- students ---------------------------------------------------------------
def test_ta07_create_student(client, sql):
    response = client.post("/students/new", STUDENT)
    assert response.status_code == 302
    row = sql("SELECT * FROM student WHERE register_number = '26BCE1201'")[0]
    assert (row["student_name"], row["department"], row["year_of_study"]) == ("Rahul Verma", "CSE", 1)
    assert "Student 26BCE1201 added." in text(client.get("/students/"))


def test_ta08_student_validation_errors_are_shown_and_nothing_is_saved(client, sql):
    bad = {"student_name": "", "register_number": "12345", "department": "CSE",
           "year_of_study": "9", "email": "not-an-email"}
    response = client.post("/students/new", bad)
    page = text(response)
    assert response.status_code == 400
    assert "Name is required." in page
    assert "Register number must look like 24BCE1012." in page
    assert "Year of study must be at most 5." in page
    assert "E-mail must look like name@example.com." in page
    assert sql("SELECT COUNT(*) AS n FROM student")[0]["n"] == 10


def test_ta09_duplicate_register_number_gives_friendly_message(client, sql):
    response = client.post("/students/new", dict(STUDENT, register_number="24BCE1012"))
    assert response.status_code == 400
    assert "A student with this register number already exists." in text(response)
    assert sql("SELECT COUNT(*) AS n FROM student")[0]["n"] == 10


def test_ta10_update_student(client, sql):
    data = {"student_name": "Aarav Menon", "register_number": "24BCE1012", "department": "CSE",
            "year_of_study": "4", "email": "aarav.m@students.example.edu"}
    assert client.post("/students/1/edit", data).status_code == 302
    row = sql("SELECT year_of_study, email FROM student WHERE student_id = 1")[0]
    assert row == {"year_of_study": 4, "email": "aarav.m@students.example.edu"}


def test_ta11_delete_student_without_history_succeeds_with_history_is_blocked(client, sql):
    assert client.post("/students/10/delete").status_code == 302          # Nisha: no allocations
    assert sql("SELECT COUNT(*) AS n FROM student WHERE student_id = 10")[0]["n"] == 0

    response = client.post("/students/1/delete", follow_redirects=True)  # Aarav: has history
    assert "cannot be deleted because other records refer to it" in text(response)
    assert sql("SELECT COUNT(*) AS n FROM student WHERE student_id = 1")[0]["n"] == 1


# ---- equipment ----------------------------------------------------------------
def test_ta12_create_and_edit_equipment(client, sql):
    data = {"equipment_name": "Function Generator", "serial_number": "fgn-01-0021",
            "category_id": "5", "lab_id": "2", "purchase_id": "3", "equipment_condition": "New"}
    response = client.post("/equipment/new", data)
    assert response.status_code == 302
    row = sql("SELECT * FROM equipment WHERE serial_number = 'FGN-01-0021'")[0]
    assert (row["availability_status"], row["equipment_condition"]) == ("Available", "New")

    edit = dict(data, lab_id="4")
    del edit["equipment_condition"]
    assert client.post(f"/equipment/{row['equipment_id']}/edit", edit).status_code == 302
    assert sql("SELECT lab_id FROM equipment WHERE serial_number = 'FGN-01-0021'")[0]["lab_id"] == 4


def test_ta13_duplicate_serial_and_missing_fields(client, sql):
    data = {"equipment_name": "Copy", "serial_number": "OSC-DS1-0001", "category_id": "1",
            "lab_id": "2", "purchase_id": "1", "equipment_condition": "Good"}
    response = client.post("/equipment/new", data)
    assert response.status_code == 400
    assert "Equipment with this serial number already exists." in text(response)

    response = client.post("/equipment/new", {"equipment_name": "No lab", "serial_number": "X-1",
                                              "category_id": "1", "purchase_id": "1",
                                              "equipment_condition": "Damaged"})
    page = text(response)
    assert response.status_code == 400
    assert "Laboratory is required." in page
    assert "Condition must be one of: New, Good, Fair." in page
    assert sql("SELECT COUNT(*) AS n FROM equipment")[0]["n"] == 20


def test_ta14_delete_equipment_with_history_is_blocked(client, sql):
    response = client.post("/equipment/1/delete", follow_redirects=True)
    assert "cannot be deleted" in text(response)
    assert sql("SELECT COUNT(*) AS n FROM equipment WHERE equipment_id = 1")[0]["n"] == 1


# ---- master data ----------------------------------------------------------------
def test_ta15_lab_crud(client, sql):
    data = {"lab_name": "Robotics Lab", "location": "Block D, Room 105", "capacity": "20", "lab_type": "Robotics"}
    assert client.post("/labs/new", data).status_code == 302
    lab_id = sql("SELECT lab_id FROM lab WHERE lab_name = 'Robotics Lab'")[0]["lab_id"]
    assert client.post(f"/labs/{lab_id}/edit", dict(data, capacity="25")).status_code == 302
    assert sql("SELECT capacity FROM lab WHERE lab_id = %s", (lab_id,))[0]["capacity"] == 25
    response = client.post("/labs/new", dict(data, lab_name="Zero Lab", capacity="0"))
    assert "Capacity must be at least 1." in text(response)
    assert client.post(f"/labs/{lab_id}/delete").status_code == 302
    assert sql("SELECT COUNT(*) AS n FROM lab")[0]["n"] == 4
    client.post("/labs/1/delete")                       # lab 1 holds equipment
    assert sql("SELECT COUNT(*) AS n FROM lab WHERE lab_id = 1")[0]["n"] == 1


def test_ta16_category_crud(client, sql):
    assert client.post("/categories/new", {"category_name": "Signal Generator", "description": ""}).status_code == 302
    cid = sql("SELECT category_id, description FROM equipment_category WHERE category_name = 'Signal Generator'")[0]
    assert cid["description"] is None                   # optional field stored as NULL
    response = client.post("/categories/new", {"category_name": "Multimeter"})
    assert "A category with this name already exists." in text(response)
    assert client.post(f"/categories/{cid['category_id']}/delete").status_code == 302
    assert sql("SELECT COUNT(*) AS n FROM equipment_category")[0]["n"] == 6


def test_ta17_supplier_validation_and_crud(client, sql):
    bad = {"supplier_name": "Nova Labs", "contact_number": "12-34", "email": "x@y"}
    page = text(client.post("/suppliers/new", bad))
    assert "Contact number must be 10-14 digits" in page
    assert "E-mail must look like name@example.com." in page
    good = {"supplier_name": "Nova Labs", "contact_number": "+919000000105", "email": "", "address": ""}
    assert client.post("/suppliers/new", good).status_code == 302
    row = sql("SELECT supplier_id, email FROM supplier WHERE supplier_name = 'Nova Labs'")[0]
    assert row["email"] is None
    assert client.post(f"/suppliers/{row['supplier_id']}/delete").status_code == 302
    client.post("/suppliers/1/delete")                  # has purchases -> blocked
    assert sql("SELECT COUNT(*) AS n FROM supplier")[0]["n"] == 4


def test_ta18_staff_crud(client, sql):
    data = {"staff_name": "Meena Das", "designation": "Lab Assistant", "department": "Physics",
            "contact_number": "9000000205", "email": "meena.das@staff.example.edu"}
    assert client.post("/staff/new", data).status_code == 302
    sid = sql("SELECT staff_id FROM lab_staff WHERE email = 'meena.das@staff.example.edu'")[0]["staff_id"]
    assert client.post(f"/staff/{sid}/edit", dict(data, designation="Senior Lab Assistant")).status_code == 302
    assert sql("SELECT designation FROM lab_staff WHERE staff_id = %s", (sid,))[0]["designation"] == "Senior Lab Assistant"
    dup = text(client.post("/staff/new", dict(data, staff_name="Other")))
    assert "A staff member with this e-mail address already exists." in dup
    assert client.post(f"/staff/{sid}/delete").status_code == 302
    assert sql("SELECT COUNT(*) AS n FROM lab_staff")[0]["n"] == 4


def test_ta19_purchase_rules(client, sql):
    data = {"supplier_id": "4", "purchase_date": "2026-10-09", "invoice_number": "zns-2026-0099",
            "total_amount": "12500.50", "purchase_status": "Ordered"}
    assert client.post("/purchases/new", data).status_code == 302
    assert sql("SELECT total_amount FROM purchase WHERE invoice_number = 'ZNS-2026-0099'")[0]["total_amount"] == 12500.50

    page = text(client.post("/purchases/new", dict(data, invoice_number="A-1", total_amount="0",
                                                    purchase_date="2026-12-01")))
    assert "Total amount must be greater than 0." in page
    assert "Purchase date cannot be after 2026-10-10." in page

    # Purchase 1 already has 4 equipment items, so it must stay 'Received'.
    original = sql("SELECT * FROM purchase WHERE purchase_id = 1")[0]
    edit = {"supplier_id": "1", "purchase_date": "2025-06-10", "invoice_number": "ASI-2025-0141",
            "total_amount": "105000.00", "purchase_status": "Cancelled"}
    page = text(client.post("/purchases/1/edit", edit))
    assert "4 equipment item(s) already belong to this purchase" in page
    assert sql("SELECT purchase_status FROM purchase WHERE purchase_id = 1")[0]["purchase_status"] == original["purchase_status"]
