"""Home page: inventory summary, overdue loans and open maintenance."""
from flask import Blueprint, render_template

from .. import db, today

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    status_counts = db.query_all(
        "SELECT availability_status, COUNT(*) AS n FROM equipment GROUP BY availability_status")
    counts = {row["availability_status"]: row["n"] for row in status_counts}

    totals = db.query_one(
        "SELECT (SELECT COUNT(*) FROM equipment) AS equipment, "
        "       (SELECT COUNT(*) FROM student) AS students, "
        "       (SELECT COUNT(*) FROM vw_outstanding_allocations) AS outstanding, "
        "       (SELECT COUNT(*) FROM vw_outstanding_allocations "
        "         WHERE expected_return_date < %s) AS overdue",
        (today(),))

    overdue = db.query_all(
        "SELECT allocation_id, student_name, register_number, serial_number, equipment_name, "
        "       expected_return_date, DATEDIFF(%s, expected_return_date) AS days_overdue "
        "FROM vw_outstanding_allocations WHERE expected_return_date < %s "
        "ORDER BY days_overdue DESC", (today(), today()))

    open_jobs = db.query_all(
        "SELECT maintenance_id, maintenance_date, serial_number, equipment_name, "
        "       maintenance_type, maintenance_status, performed_by "
        "FROM vw_maintenance_history WHERE maintenance_status <> 'Completed' "
        "ORDER BY FIELD(maintenance_status, 'In Progress', 'Scheduled'), maintenance_date")

    return render_template("dashboard.html", counts=counts, totals=totals,
                           overdue=overdue, open_jobs=open_jobs)
