"""Student portal ("My equipment"), for signed-in students only.

A student sees ONLY their own loans and requests, plus a read-only list of
equipment that is available now. Every query here is filtered by the
student_id of the signed-in session (g.student), never by a value from the
URL or the form, so one student can never see or change another's data.
"""
from datetime import timedelta

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .. import db, today
from ..validators import Form
from . import try_db

bp = Blueprint("portal", __name__, url_prefix="/my")

MAX_PENDING = 3          # open requests per student
MAX_DAYS_AHEAD = 30      # a request can start at most this far in the future
MAX_LOAN_DAYS = 14       # longest loan a student can ask for


@bp.route("/")
def home():
    me = g.student
    loans = db.query_all(
        "SELECT h.*, CASE WHEN h.allocation_status = 'Issued' AND h.expected_return_date < %s "
        "                 THEN DATEDIFF(%s, h.expected_return_date) END AS days_overdue "
        "FROM vw_allocation_history h WHERE h.register_number = %s "
        "ORDER BY h.allocation_status = 'Issued' DESC, h.allocation_date DESC, h.allocation_id DESC",
        (today(), today(), me["register_number"]))
    requests_ = db.query_all(
        "SELECT r.request_id, r.requested_from, r.requested_until, r.purpose, r.request_status, "
        "       r.created_at, r.decided_at, r.decision_note, e.equipment_name, e.serial_number "
        "FROM equipment_request r JOIN equipment e ON e.equipment_id = r.equipment_id "
        "WHERE r.student_id = %s ORDER BY r.created_at DESC, r.request_id DESC LIMIT 20",
        (me["student_id"],))
    q = request.args.get("q", "").strip()[:60]
    sql = ("SELECT e.equipment_id, e.equipment_name, e.serial_number, e.equipment_condition, "
           "       c.category_name, l.lab_name, "
           "       EXISTS (SELECT 1 FROM equipment_request r WHERE r.equipment_id = e.equipment_id "
           "               AND r.student_id = %s AND r.request_status = 'Pending') AS requested "
           "FROM equipment e JOIN equipment_category c ON c.category_id = e.category_id "
           "JOIN lab l ON l.lab_id = e.lab_id WHERE e.availability_status = 'Available'")
    params = [me["student_id"]]
    if q:
        sql += " AND (e.equipment_name LIKE %s OR c.category_name LIKE %s)"
        params += [f"%{q}%", f"%{q}%"]
    available = db.query_all(sql + " ORDER BY e.equipment_name, e.serial_number", params)
    pending = sum(1 for r in requests_ if r["request_status"] == "Pending")
    return render_template("portal/home.html", loans=loans, requests=requests_, available=available,
                           q=q, pending=pending, max_pending=MAX_PENDING)


@bp.route("/request/<int:equipment_id>", methods=["GET", "POST"])
def new_request(equipment_id):
    item = db.query_one(
        "SELECT e.equipment_id, e.equipment_name, e.serial_number, e.availability_status, l.lab_name "
        "FROM equipment e JOIN lab l ON l.lab_id = e.lab_id WHERE e.equipment_id = %s", (equipment_id,))
    if item is None:
        abort(404, "Equipment not found.")
    if item["availability_status"] != "Available":
        flash(f"{item['serial_number']} is not available right now.", "error")
        return redirect(url_for("portal.home"))

    def show(values, errors=None, status=200):
        return render_template("portal/request.html", item=item, values=values, errors=errors or {},
                               max_days=MAX_LOAN_DAYS), status

    start = today()
    if request.method == "GET":
        return show({"requested_from": start.isoformat(),
                     "requested_until": (start + timedelta(days=7)).isoformat(), "purpose": ""})

    form = Form(request.form)
    begin = form.date("requested_from", "From", not_before=start,
                      not_after=start + timedelta(days=MAX_DAYS_AHEAD))
    until = form.date("requested_until", "Until")
    purpose = form.text("purpose", "Purpose", max_len=255)
    if begin and until:
        if until < begin:
            form.error("requested_until", "Until must be on or after From.")
        elif (until - begin).days > MAX_LOAN_DAYS:
            form.error("requested_until", f"A loan can be at most {MAX_LOAN_DAYS} days.")
    open_count = db.query_one("SELECT COUNT(*) AS n FROM equipment_request "
                              "WHERE student_id = %s AND request_status = 'Pending'",
                              (g.student["student_id"],))["n"]
    if open_count >= MAX_PENDING:
        form.error("purpose", f"You already have {MAX_PENDING} open requests. "
                              "Wait for a decision or cancel one first.")
    if not form.ok:
        return show(request.form, form.errors, 400)

    message = try_db(lambda: db.execute(
        "INSERT INTO equipment_request (student_id, equipment_id, requested_from, requested_until, purpose) "
        "VALUES (%s, %s, %s, %s, %s)",
        (g.student["student_id"], equipment_id, begin, until, purpose)))
    if message:
        flash(message, "error")
        return show(request.form, status=400)
    flash(f"Request for {item['serial_number']} sent. Lab staff will approve or reject it.", "success")
    return redirect(url_for("portal.home"))


@bp.route("/requests/<int:request_id>/cancel", methods=["POST"])
def cancel_request(request_id):
    # Filtered by the signed-in student: another student's request is "not found".
    row = db.query_one("SELECT request_status FROM equipment_request "
                       "WHERE request_id = %s AND student_id = %s", (request_id, g.student["student_id"]))
    if row is None:
        abort(404, "Request not found.")
    if row["request_status"] != "Pending":
        flash("Only a pending request can be cancelled.", "error")
    else:
        db.execute("UPDATE equipment_request SET request_status = 'Cancelled', decided_at = NOW() "
                   "WHERE request_id = %s AND student_id = %s AND request_status = 'Pending'",
                   (request_id, g.student["student_id"]))
        flash("Request cancelled.", "success")
    return redirect(url_for("portal.home"))
