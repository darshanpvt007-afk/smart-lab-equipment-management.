"""Student borrowing requests, for staff who may issue equipment.

Approve = issue the item now through sp_allocate_equipment (the same
transaction and checks as the Issue form), then mark the request Approved
with the new allocation id. Reject = record the decision and an optional
note the student can read.
"""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .. import db, today
from ..validators import Form
from . import staff_options, try_db

bp = Blueprint("requests", __name__, url_prefix="/requests")


def load_pending(request_id):
    row = db.query_one("SELECT * FROM equipment_request WHERE request_id = %s", (request_id,))
    if row is None:
        abort(404, "Request not found.")
    return row


@bp.route("/")
def list_requests():
    show = "all" if request.args.get("show") == "all" else "pending"
    where = "" if show == "all" else "WHERE r.request_status = 'Pending' "
    rows = db.query_all(
        "SELECT r.*, s.student_name, s.register_number, e.equipment_name, e.serial_number, "
        "       e.availability_status, u.username AS decided_by, "
        "       (SELECT COUNT(*) FROM vw_outstanding_allocations o "
        "         WHERE o.student_id = r.student_id AND o.expected_return_date < %s) AS student_overdue "
        "FROM equipment_request r "
        "JOIN student s ON s.student_id = r.student_id "
        "JOIN equipment e ON e.equipment_id = r.equipment_id "
        "LEFT JOIN app_user u ON u.user_id = r.decided_by_user_id "
        f"{where}ORDER BY r.request_status = 'Pending' DESC, r.created_at, r.request_id",
        (today(),))
    return render_template("requests/list.html", rows=rows, show=show, staff=staff_options(),
                           default_staff=(g.user or {}).get("staff_id"))


@bp.route("/<int:request_id>/approve", methods=["POST"])
def approve(request_id):
    req = load_pending(request_id)
    if req["request_status"] != "Pending":
        flash(f"Request #{request_id} has already been decided.", "error")
        return redirect(url_for("requests.list_requests"))
    form = Form(request.form)
    staff_id = form.integer("staff_id", "Issued by")
    due = form.date("expected_return_date", "Due date", not_before=today())
    if not form.ok:
        flash(" ".join(form.errors.values()), "error")
        return redirect(url_for("requests.list_requests"))

    result = {}

    def allocate():
        result["args"] = db.call_procedure(
            "sp_allocate_equipment", (req["equipment_id"], req["student_id"], staff_id, today(), due, 0))
    message = try_db(allocate)
    if message:
        flash(f"Request #{request_id} not approved: {message}", "error")
        return redirect(url_for("requests.list_requests"))
    allocation_id = result["args"][5]
    db.execute("UPDATE equipment_request SET request_status = 'Approved', allocation_id = %s, "
               "decided_by_user_id = %s, decided_at = NOW() "
               "WHERE request_id = %s AND request_status = 'Pending'",
               (allocation_id, g.user["user_id"], request_id))
    flash(f"Request #{request_id} approved: equipment issued (allocation #{allocation_id}).", "success")
    return redirect(url_for("requests.list_requests"))


@bp.route("/<int:request_id>/reject", methods=["POST"])
def reject(request_id):
    req = load_pending(request_id)
    if req["request_status"] != "Pending":
        flash(f"Request #{request_id} has already been decided.", "error")
        return redirect(url_for("requests.list_requests"))
    note = Form(request.form).text("decision_note", "Note", required=False, max_len=255)
    message = try_db(lambda: db.execute(
        "UPDATE equipment_request SET request_status = 'Rejected', decision_note = %s, "
        "decided_by_user_id = %s, decided_at = NOW() WHERE request_id = %s AND request_status = 'Pending'",
        (note, g.user["user_id"], request_id)))
    flash(message or f"Request #{request_id} rejected.", "error" if message else "success")
    return redirect(url_for("requests.list_requests"))
