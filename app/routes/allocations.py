"""Equipment allocation (issue) and return.

Both operations call the stored procedures in sql/11_transaction_procedures.sql,
which run as one transaction, lock the equipment row and keep
equipment.availability_status consistent. The checks here only give the
user early, field-level messages; the procedures are the final guard.
"""
from datetime import timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import db, today
from ..validators import RETURN_CONDITIONS, Form
from . import staff_options, try_db

bp = Blueprint("allocations", __name__, url_prefix="/allocations")

FILTERS = {
    "all": ("", ()),
    "issued": ("WHERE allocation_status = 'Issued'", ()),
    "overdue": ("WHERE allocation_status = 'Issued' AND expected_return_date < %s", None),
    "returned": ("WHERE allocation_status = 'Returned'", ()),
}


QUICK_PICKS = ((3, "3 days"), (7, "1 week"), (14, "2 weeks"))


@bp.route("/")
def list_allocations():
    show = request.args.get("show", "issued")
    if show not in FILTERS:
        show = "issued"
    # `where` is one of the fixed strings in FILTERS (never user text), so
    # putting it into the SQL is safe; the date still goes in as a parameter.
    where, params = FILTERS[show]
    if params is None:
        params = (today(),)
    rows = db.query_all(
        "SELECT *, CASE WHEN allocation_status = 'Issued' AND expected_return_date < %s "
        "               THEN DATEDIFF(%s, expected_return_date) END AS days_overdue "
        f"FROM vw_allocation_history {where} ORDER BY allocation_date DESC, allocation_id DESC",
        (today(), today(), *params))
    return render_template("allocations/list.html", rows=rows, show=show)


def render_issue_form(item, errors=None, status=200):
    # Extra facts per option feed the "pre-issue checks" panel in the browser;
    # sp_allocate_equipment still re-checks everything when the form is saved.
    equipment = db.query_all(
        "SELECT e.equipment_id AS id, e.serial_number, e.equipment_name, e.equipment_condition, "
        "       l.lab_name, CONCAT(e.serial_number, ' - ', e.equipment_name, ' (', l.lab_name, ')') AS name "
        "FROM equipment e JOIN lab l ON l.lab_id = e.lab_id "
        "WHERE e.availability_status = 'Available' ORDER BY e.equipment_name, e.serial_number")
    students = db.query_all(
        "SELECT s.student_id AS id, s.student_name, s.register_number, s.department, s.year_of_study, "
        "       CONCAT(s.register_number, ' - ', s.student_name) AS name, "
        "       COUNT(o.allocation_id) AS holding, "
        "       COALESCE(SUM(o.expected_return_date < %s), 0) AS overdue "
        "FROM student s LEFT JOIN vw_outstanding_allocations o ON o.student_id = s.student_id "
        "GROUP BY s.student_id, s.student_name, s.register_number, s.department, s.year_of_study "
        "ORDER BY s.register_number", (today(),))
    unavailable = db.query_one(
        "SELECT COUNT(*) AS n FROM equipment WHERE availability_status <> 'Available'")["n"]
    return render_template("allocations/issue.html", item=item, errors=errors or {},
                           equipment=equipment, students=students, staff=staff_options(),
                           unavailable=unavailable, quick_picks=QUICK_PICKS), status


@bp.route("/new", methods=["GET", "POST"])
def issue():
    if request.method == "GET":
        defaults = {"equipment_id": request.args.get("equipment_id", ""),
                    "allocation_date": today().isoformat(),
                    "expected_return_date": (today() + timedelta(days=7)).isoformat()}
        return render_issue_form(defaults)

    form = Form(request.form)
    equipment_id = form.integer("equipment_id", "Equipment")
    student_id = form.integer("student_id", "Student")
    staff_id = form.integer("staff_id", "Issued by")
    issued_on = form.date("allocation_date", "Allocation date", not_after=today())
    due = form.date("expected_return_date", "Expected return date")
    if issued_on and due and due < issued_on:
        form.error("expected_return_date", "Expected return date must be on or after the allocation date.")
    if not form.ok:
        return render_issue_form(request.form, form.errors, 400)

    result = {}
    def allocate():
        result["args"] = db.call_procedure(
            "sp_allocate_equipment", (equipment_id, student_id, staff_id, issued_on, due, 0))
    message = try_db(allocate)
    if message:
        flash(message, "error")
        return render_issue_form(request.form, status=400)
    flash(f"Equipment issued (allocation #{result['args'][5]}).", "success")
    return redirect(url_for("allocations.list_allocations", show="issued"))


@bp.route("/<int:allocation_id>/return", methods=["GET", "POST"])
def return_equipment(allocation_id):
    allocation = db.query_one("SELECT * FROM vw_allocation_history WHERE allocation_id = %s", (allocation_id,))
    if allocation is None:
        abort(404, "Allocation not found.")
    if allocation["allocation_status"] != "Issued":
        flash(f"Allocation #{allocation_id} has already been returned.", "error")
        return redirect(url_for("allocations.list_allocations", show="returned"))

    def show(item, errors=None, status=200):
        return render_template("allocations/return.html", allocation=allocation, item=item,
                               errors=errors or {}, conditions=RETURN_CONDITIONS), status

    if request.method == "GET":
        return show({"return_date": today().isoformat(), "return_condition": "Good"})

    form = Form(request.form)
    returned_on = form.date("return_date", "Return date", not_after=today(),
                            not_before=allocation["allocation_date"])
    condition = form.choice("return_condition", "Condition", RETURN_CONDITIONS)
    remarks = form.text("remarks", "Remarks", required=False, max_len=255)
    if not form.ok:
        return show(request.form, form.errors, 400)

    message = try_db(lambda: db.call_procedure(
        "sp_return_equipment", (allocation_id, returned_on, condition, remarks)))
    if message:
        flash(message, "error")
        return show(request.form, status=400)
    note = " It is marked Unavailable until repaired." if condition == "Damaged" else ""
    flash(f"Return of {allocation['serial_number']} recorded.{note}", "success")
    return redirect(url_for("allocations.list_allocations", show="issued"))
