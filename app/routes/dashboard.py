"""Home page (operations overview) and the global search in the top bar."""
from datetime import date, timedelta

from flask import Blueprint, render_template, request

from .. import activity, db, today

bp = Blueprint("dashboard", __name__)

MONTHS_SHOWN = 4


def month_starts(ref, count):
    """First day of the `count` months ending with ref's month, oldest first."""
    starts, y, m = [], ref.year, ref.month
    for _ in range(count):
        starts.append(date(y, m, 1))
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    return starts[::-1]


@bp.route("/")
def index():
    ref = today()
    status_counts = db.query_all(
        "SELECT availability_status, COUNT(*) AS n FROM equipment GROUP BY availability_status")
    counts = {row["availability_status"]: row["n"] for row in status_counts}

    totals = db.query_one(
        "SELECT (SELECT COUNT(*) FROM equipment) AS equipment, "
        "       (SELECT COUNT(*) FROM vw_outstanding_allocations) AS outstanding, "
        "       (SELECT COUNT(*) FROM vw_outstanding_allocations "
        "         WHERE expected_return_date < %s) AS overdue, "
        "       (SELECT COUNT(*) FROM equipment_allocation "
        "         WHERE allocation_date BETWEEN %s AND %s) AS issued_last_7_days, "
        "       (SELECT COUNT(*) FROM maintenance WHERE maintenance_status = 'In Progress') AS jobs_in_progress, "
        "       (SELECT COUNT(*) FROM maintenance WHERE maintenance_status = 'Scheduled') AS jobs_scheduled, "
        "       (SELECT SUM(maintenance_cost) FROM maintenance "
        "         WHERE maintenance_status = 'In Progress') AS cost_committed, "
        "       (SELECT SUM(maintenance_cost) FROM maintenance "
        "         WHERE maintenance_status = 'Completed') AS cost_spent",
        (ref, ref - timedelta(days=6), ref))

    overdue = db.query_all(
        "SELECT o.allocation_id, o.student_id, o.student_name, o.register_number, s.department, "
        "       o.equipment_id, o.serial_number, o.equipment_name, o.issued_by, "
        "       o.expected_return_date, DATEDIFF(%s, o.expected_return_date) AS days_overdue "
        "FROM vw_outstanding_allocations o JOIN student s ON s.student_id = o.student_id "
        "WHERE o.expected_return_date < %s ORDER BY days_overdue DESC", (ref, ref))

    due_soon = db.query_all(
        "SELECT student_name, expected_return_date FROM vw_outstanding_allocations "
        "WHERE expected_return_date BETWEEN %s AND %s ORDER BY expected_return_date",
        (ref, ref + timedelta(days=4)))

    # Loans issued per calendar month for the last MONTHS_SHOWN months.
    starts = month_starts(ref, MONTHS_SHOWN)
    per_month = {(r["y"], r["m"]): r["n"] for r in db.query_all(
        "SELECT YEAR(allocation_date) AS y, MONTH(allocation_date) AS m, COUNT(*) AS n "
        "FROM equipment_allocation WHERE allocation_date BETWEEN %s AND %s "
        "GROUP BY YEAR(allocation_date), MONTH(allocation_date)", (starts[0], ref))}
    months = [{"label": f"{s:%b}" + (f" (1–{ref.day})" if (s.year, s.month) == (ref.year, ref.month) else ""),
               "name": f"{s:%B}", "n": per_month.get((s.year, s.month), 0)} for s in starts]
    busiest = max(months, key=lambda m: m["n"])

    labs = db.query_all(
        "SELECT l.lab_id, l.lab_name, l.location, COUNT(e.equipment_id) AS item_count, "
        "       COALESCE(SUM(e.availability_status = 'Available'), 0) AS available, "
        "       COALESCE(SUM(e.availability_status = 'Allocated'), 0) AS on_loan, "
        "       COALESCE(SUM(e.availability_status = 'Under Maintenance'), 0) AS in_repair, "
        "       COALESCE(SUM(e.availability_status = 'Unavailable'), 0) AS unavailable "
        "FROM lab l LEFT JOIN equipment e ON e.lab_id = l.lab_id "
        "GROUP BY l.lab_id, l.lab_name, l.location "
        "ORDER BY COALESCE(SUM(e.availability_status <> 'Available') / NULLIF(COUNT(e.equipment_id), 0), 0) DESC, "
        "         l.lab_name")

    feed = activity.recent(ref)
    for ev in feed:
        ev["summary"] = activity.summary(ev)

    return render_template("dashboard.html", counts=counts, totals=totals, overdue=overdue,
                           due_soon=due_soon, months=months, busiest=busiest,
                           month_max=max(busiest["n"], 1), labs=labs, feed=feed)


@bp.route("/search")
def search():
    """One search box for the most-used records (equipment, students, staff, labs)."""
    q = request.args.get("q", "").strip()
    results = {"equipment": [], "students": [], "staff": [], "labs": []}
    if q:
        like = f"%{q}%"
        results["equipment"] = db.query_all(
            "SELECT equipment_id, equipment_name, serial_number, lab_name, availability_status "
            "FROM vw_equipment_inventory WHERE equipment_name LIKE %s OR serial_number LIKE %s "
            "ORDER BY equipment_name, serial_number LIMIT 25", (like, like))
        results["students"] = db.query_all(
            "SELECT student_id, student_name, register_number, department, year_of_study FROM student "
            "WHERE student_name LIKE %s OR register_number LIKE %s OR email LIKE %s "
            "ORDER BY student_name LIMIT 25", (like, like, like))
        results["staff"] = db.query_all(
            "SELECT staff_id, staff_name, designation FROM lab_staff "
            "WHERE staff_name LIKE %s OR email LIKE %s ORDER BY staff_name LIMIT 25", (like, like))
        results["labs"] = db.query_all(
            "SELECT lab_id, lab_name, location FROM lab WHERE lab_name LIKE %s OR location LIKE %s "
            "ORDER BY lab_name LIMIT 25", (like, like))
    total = sum(len(v) for v in results.values())
    return render_template("search.html", q=q, results=results, total=total)
