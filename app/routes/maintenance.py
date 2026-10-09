"""Maintenance: schedule (INSERT), start and complete (stored procedures in
sql/12_maintenance_procedures.sql)."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import db, today
from ..validators import MAINTENANCE_STATUSES, MAINTENANCE_TYPES, Form
from . import equipment_options, staff_options, try_db

bp = Blueprint("maintenance", __name__, url_prefix="/maintenance")


@bp.route("/")
def list_jobs():
    status = request.args.get("status", "")
    if status in MAINTENANCE_STATUSES:
        rows = db.query_all("SELECT * FROM vw_maintenance_history WHERE maintenance_status = %s "
                            "ORDER BY maintenance_date DESC", (status,))
    else:
        status = ""
        rows = db.query_all("SELECT * FROM vw_maintenance_history ORDER BY maintenance_date DESC")
    return render_template("maintenance/list.html", rows=rows, status=status, statuses=MAINTENANCE_STATUSES)


def render_schedule_form(item, errors=None, status=200):
    return render_template("maintenance/schedule.html", item=item, errors=errors or {},
                           equipment=equipment_options(), staff=staff_options(),
                           types=MAINTENANCE_TYPES), status


@bp.route("/new", methods=["GET", "POST"])
def schedule():
    if request.method == "GET":
        return render_schedule_form({"equipment_id": request.args.get("equipment_id", ""),
                                     "maintenance_date": today().isoformat()})
    form = Form(request.form)
    data = (
        form.integer("equipment_id", "Equipment"),
        form.integer("staff_id", "Assigned to"),
        form.date("maintenance_date", "Planned date", not_before=today()),
        form.choice("maintenance_type", "Type", MAINTENANCE_TYPES),
        form.text("remarks", "Remarks", required=False, max_len=255),
    )
    if not form.ok:
        return render_schedule_form(request.form, form.errors, 400)
    message = try_db(lambda: db.execute(
        "INSERT INTO maintenance (equipment_id, staff_id, maintenance_date, maintenance_type, "
        "maintenance_status, remarks) VALUES (%s, %s, %s, %s, 'Scheduled', %s)", data))
    if message:
        flash(message, "error")
        return render_schedule_form(request.form, status=400)
    flash("Maintenance scheduled.", "success")
    return redirect(url_for("maintenance.list_jobs", status="Scheduled"))


def load_job(maintenance_id):
    job = db.query_one("SELECT * FROM vw_maintenance_history WHERE maintenance_id = %s", (maintenance_id,))
    if job is None:
        abort(404, "Maintenance record not found.")
    return job


@bp.route("/<int:maintenance_id>/start", methods=["POST"])
def start(maintenance_id):
    load_job(maintenance_id)
    message = try_db(lambda: db.call_procedure("sp_start_maintenance", (maintenance_id, today())))
    flash(message or f"Maintenance #{maintenance_id} started; the equipment is now Under Maintenance.",
          "error" if message else "success")
    return redirect(url_for("maintenance.list_jobs", status="In Progress"))


@bp.route("/<int:maintenance_id>/complete", methods=["GET", "POST"])
def complete(maintenance_id):
    job = load_job(maintenance_id)
    conditions = ("Good", "Fair", "Damaged")

    def show(item, errors=None, status=200):
        return render_template("maintenance/complete.html", job=job, item=item, errors=errors or {},
                               conditions=conditions), status

    if request.method == "GET":
        cost = job["maintenance_cost"]
        return show({"maintenance_cost": "" if cost is None else cost, "condition_after": "Good"})

    form = Form(request.form)
    cost = form.money("maintenance_cost", "Cost")
    condition = form.choice("condition_after", "Condition after maintenance", conditions)
    remarks = form.text("remarks", "Remarks", required=False, max_len=255)
    if not form.ok:
        return show(request.form, form.errors, 400)
    message = try_db(lambda: db.call_procedure(
        "sp_complete_maintenance", (maintenance_id, cost, condition, remarks)))
    if message:
        flash(message, "error")
        return show(request.form, status=400)
    flash(f"Maintenance #{maintenance_id} completed.", "success")
    return redirect(url_for("maintenance.list_jobs", status="Completed"))
