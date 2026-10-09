"""Lab staff: list with workload, add, edit, delete."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import db
from ..validators import Form
from . import try_db

bp = Blueprint("staff", __name__, url_prefix="/staff")


@bp.route("/")
def list_staff():
    rows = db.query_all(
        "SELECT ls.*, "
        "  (SELECT COUNT(*) FROM equipment_allocation a WHERE a.staff_id = ls.staff_id) AS issued, "
        "  (SELECT COUNT(*) FROM maintenance m WHERE m.staff_id = ls.staff_id) AS jobs "
        "FROM lab_staff ls ORDER BY ls.staff_name")
    return render_template("staff/list.html", rows=rows)


def read_form():
    form = Form(request.form)
    data = (
        form.text("staff_name", "Name", max_len=100),
        form.text("designation", "Designation", max_len=60),
        form.text("department", "Department", max_len=60),
        form.phone("contact_number"),
        form.email("email"),
    )
    return form, data


def show_form(item, errors, is_new, status=200):
    return render_template("staff/form.html", item=item, errors=errors, is_new=is_new), status


@bp.route("/new", methods=["GET", "POST"])
def create():
    if request.method == "GET":
        return show_form({}, {}, True)
    form, data = read_form()
    if not form.ok:
        return show_form(request.form, form.errors, True, 400)
    message = try_db(lambda: db.execute(
        "INSERT INTO lab_staff (staff_name, designation, department, contact_number, email) "
        "VALUES (%s, %s, %s, %s, %s)", data))
    if message:
        flash(message, "error")
        return show_form(request.form, {}, True, 400)
    flash(f"Staff member {data[0]} added.", "success")
    return redirect(url_for("staff.list_staff"))


@bp.route("/<int:staff_id>/edit", methods=["GET", "POST"])
def edit(staff_id):
    item = db.query_one("SELECT * FROM lab_staff WHERE staff_id = %s", (staff_id,))
    if item is None:
        abort(404, "Staff member not found.")
    if request.method == "GET":
        return show_form(item, {}, False)
    form, data = read_form()
    if not form.ok:
        return show_form(request.form, form.errors, False, 400)
    message = try_db(lambda: db.execute(
        "UPDATE lab_staff SET staff_name = %s, designation = %s, department = %s, "
        "contact_number = %s, email = %s WHERE staff_id = %s", (*data, staff_id)))
    if message:
        flash(message, "error")
        return show_form(request.form, {}, False, 400)
    flash("Staff member updated.", "success")
    return redirect(url_for("staff.list_staff"))


@bp.route("/<int:staff_id>/delete", methods=["POST"])
def delete(staff_id):
    message = try_db(lambda: db.execute("DELETE FROM lab_staff WHERE staff_id = %s", (staff_id,)))
    flash(message or "Staff member deleted.", "error" if message else "success")
    return redirect(url_for("staff.list_staff"))
