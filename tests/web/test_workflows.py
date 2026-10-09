"""TA20-TA27: issue, return and maintenance workflows through the web app
(they call the stored procedures) and data consistency afterwards."""

ISSUE = {"equipment_id": "15", "student_id": "10", "staff_id": "1",
         "allocation_date": "2026-10-10", "expected_return_date": "2026-10-17"}


def text(response):
    return response.get_data(as_text=True)


def state(sql, equipment_id):
    return sql("SELECT availability_status, equipment_condition FROM equipment WHERE equipment_id = %s",
               (equipment_id,))[0]


def test_ta20_issue_available_equipment(client, sql):
    response = client.post("/allocations/new", ISSUE, follow_redirects=True)
    assert "Equipment issued (allocation #21)." in text(response)
    row = sql("SELECT * FROM equipment_allocation WHERE allocation_id = 21")[0]
    assert (row["equipment_id"], row["student_id"], row["allocation_status"]) == (15, 10, "Issued")
    assert state(sql, 15)["availability_status"] == "Allocated"


def test_ta21_issue_refused_for_unavailable_items(client, sql):
    for equipment_id, status in ((1, "Allocated"), (3, "Under Maintenance"), (9, "Unavailable")):
        response = client.post("/allocations/new", dict(ISSUE, equipment_id=str(equipment_id)))
        assert response.status_code == 400
        assert f"equipment {equipment_id} is {status}, not Available" in text(response)
    assert sql("SELECT COUNT(*) AS n FROM equipment_allocation")[0]["n"] == 20


def test_ta22_issue_form_validation(client, sql):
    page = text(client.post("/allocations/new", dict(ISSUE, expected_return_date="2026-10-01")))
    assert "Expected return date must be on or after the allocation date." in page
    page = text(client.post("/allocations/new", dict(ISSUE, allocation_date="2026-11-01",
                                                     expected_return_date="2026-11-08")))
    assert "Allocation date cannot be after 2026-10-10." in page
    page = text(client.post("/allocations/new", dict(ISSUE, student_id="")))
    assert "Student is required." in page
    assert sql("SELECT COUNT(*) AS n FROM equipment_allocation")[0]["n"] == 20


def test_ta23_return_in_good_condition(client, sql):
    data = {"return_date": "2026-10-10", "return_condition": "Good", "remarks": "Complete"}
    response = client.post("/allocations/17/return", data, follow_redirects=True)
    assert "Return of OSC-DS1-0001 recorded." in text(response)
    assert sql("SELECT allocation_status FROM equipment_allocation WHERE allocation_id = 17")[0]["allocation_status"] == "Returned"
    assert sql("SELECT return_condition FROM equipment_return WHERE allocation_id = 17")[0]["return_condition"] == "Good"
    assert state(sql, 1) == {"availability_status": "Available", "equipment_condition": "Good"}

    # A second return of the same allocation is refused.
    response = client.post("/allocations/17/return", data, follow_redirects=True)
    assert "Allocation #17 has already been returned." in text(response)
    assert sql("SELECT COUNT(*) AS n FROM equipment_return WHERE allocation_id = 17")[0]["n"] == 1


def test_ta24_return_validation_and_damaged_return(client, sql):
    page = text(client.post("/allocations/18/return", {"return_date": "2026-10-01", "return_condition": "Good"}))
    assert "Return date cannot be before 2026-10-05." in page
    assert sql("SELECT allocation_status FROM equipment_allocation WHERE allocation_id = 18")[0]["allocation_status"] == "Issued"

    response = client.post("/allocations/19/return", {"return_date": "2026-10-10", "return_condition": "Damaged",
                                                      "remarks": "Cracked case"}, follow_redirects=True)
    assert "marked Unavailable until repaired" in text(response)
    assert state(sql, 10) == {"availability_status": "Unavailable", "equipment_condition": "Damaged"}


def test_ta25_maintenance_schedule_start_complete(client, sql):
    data = {"equipment_id": "11", "staff_id": "3", "maintenance_date": "2026-10-10",
            "maintenance_type": "Preventive", "remarks": "Firmware update"}
    assert client.post("/maintenance/new", data).status_code == 302
    job = sql("SELECT * FROM maintenance WHERE equipment_id = 11")[0]
    assert job["maintenance_status"] == "Scheduled"
    assert state(sql, 11)["availability_status"] == "Available"      # scheduling alone changes nothing

    client.post(f"/maintenance/{job['maintenance_id']}/start")
    assert sql("SELECT maintenance_status FROM maintenance WHERE maintenance_id = %s",
               (job["maintenance_id"],))[0]["maintenance_status"] == "In Progress"
    assert state(sql, 11)["availability_status"] == "Under Maintenance"

    page = text(client.post(f"/maintenance/{job['maintenance_id']}/complete",
                            {"maintenance_cost": "-5", "condition_after": "Good"}))
    assert "Cost cannot be negative." in page

    client.post(f"/maintenance/{job['maintenance_id']}/complete",
                {"maintenance_cost": "350.00", "condition_after": "Good", "remarks": ""})
    done = sql("SELECT * FROM maintenance WHERE maintenance_id = %s", (job["maintenance_id"],))[0]
    assert (done["maintenance_status"], float(done["maintenance_cost"]), done["remarks"]) == \
           ("Completed", 350.0, "Firmware update")                      # empty remarks keep the old text
    assert state(sql, 11) == {"availability_status": "Available", "equipment_condition": "Good"}


def test_ta26_maintenance_refusals(client, sql):
    # Cannot start work on equipment that is with a student (equipment 1 is Allocated).
    client.post("/maintenance/new", {"equipment_id": "1", "staff_id": "2", "maintenance_date": "2026-10-10",
                                     "maintenance_type": "Calibration"})
    job_id = sql("SELECT MAX(maintenance_id) AS id FROM maintenance")[0]["id"]
    response = client.post(f"/maintenance/{job_id}/start", follow_redirects=True)
    assert "currently allocated to a student" in text(response)
    assert sql("SELECT maintenance_status FROM maintenance WHERE maintenance_id = %s",
               (job_id,))[0]["maintenance_status"] == "Scheduled"

    # Cannot schedule in the past.
    page = text(client.post("/maintenance/new", {"equipment_id": "2", "staff_id": "2",
                                                 "maintenance_date": "2026-01-01", "maintenance_type": "Repair"}))
    assert "Planned date cannot be before 2026-10-10." in page

    # A completed job cannot be started again.
    response = client.post("/maintenance/1/start", follow_redirects=True)
    assert "maintenance 1 is Completed, not Scheduled" in text(response)


def test_ta27_database_stays_consistent_after_workflows(client, sql):
    client.post("/allocations/new", ISSUE)
    client.post("/allocations/21/return", {"return_date": "2026-10-10", "return_condition": "Fair"})
    client.post("/allocations/16/return", {"return_date": "2026-10-10", "return_condition": "Damaged"})
    client.post("/maintenance/new", {"equipment_id": "4", "staff_id": "2", "maintenance_date": "2026-10-10",
                                     "maintenance_type": "Repair"})
    job_id = sql("SELECT MAX(maintenance_id) AS id FROM maintenance")[0]["id"]
    client.post(f"/maintenance/{job_id}/start")
    client.post(f"/maintenance/{job_id}/complete", {"maintenance_cost": "600", "condition_after": "Good"})
    client.post("/maintenance/8/complete", {"maintenance_cost": "8500", "condition_after": "Good"})

    # Validation checks V06, V07, V08, V10, V11, V12 from sql/09 must all be empty.
    v10 = sql("""SELECT e.equipment_id FROM equipment e
                 LEFT JOIN equipment_allocation a ON a.equipment_id = e.equipment_id AND a.allocation_status = 'Issued'
                 GROUP BY e.equipment_id, e.availability_status
                 HAVING (e.availability_status = 'Allocated' AND COUNT(a.allocation_id) = 0)
                     OR (e.availability_status <> 'Allocated' AND COUNT(a.allocation_id) > 0)""")
    v11 = sql("""SELECT e.equipment_id FROM equipment e
                 LEFT JOIN maintenance m ON m.equipment_id = e.equipment_id AND m.maintenance_status = 'In Progress'
                 GROUP BY e.equipment_id, e.availability_status
                 HAVING (e.availability_status = 'Under Maintenance' AND COUNT(m.maintenance_id) = 0)
                     OR (e.availability_status <> 'Under Maintenance' AND COUNT(m.maintenance_id) > 0)""")
    v06_v07 = sql("""SELECT a.allocation_id FROM equipment_allocation a
                     LEFT JOIN equipment_return r ON r.allocation_id = a.allocation_id
                     WHERE (a.allocation_status = 'Returned') <> (r.return_id IS NOT NULL)""")
    v08 = sql("""SELECT equipment_id FROM equipment_allocation WHERE allocation_status = 'Issued'
                 GROUP BY equipment_id HAVING COUNT(*) > 1""")
    v12 = sql("SELECT equipment_id FROM equipment WHERE equipment_condition = 'Damaged' AND availability_status = 'Available'")
    assert (v10, v11, v06_v07, v08, v12) == ([], [], [], [], [])
    assert state(sql, 4) == {"availability_status": "Available", "equipment_condition": "Good"}
    assert state(sql, 3) == {"availability_status": "Available", "equipment_condition": "Good"}
