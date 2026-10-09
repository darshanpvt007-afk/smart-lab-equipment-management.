"""Laboratories: list with equipment counts, add, edit, delete."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import db
from ..validators import Form
from . import try_db

bp = Blueprint("labs", __name__, url_prefix="/labs")


@bp.route("/")
def list_labs():
    rows = db.query_all(
        "SELECT l.lab_id, l.lab_name, l.location, l.capacity, l.lab_type, "
        "       COUNT(e.equipment_id) AS equipment_count, "
        "       SUM(e.availability_status = 'Available') AS available "
        "FROM lab l LEFT JOIN equipment e ON e.lab_id = l.lab_id "
        "GROUP BY l.lab_id, l.lab_name, l.location, l.capacity, l.lab_type "
        "ORDER BY l.lab_name")
    return render_template("labs/list.html", rows=rows)


def read_form():
    form = Form(request.form)
    data = (
        form.text("lab_name", "Lab name", max_len=100),
        form.text("location", "Location", max_len=150),
        form.integer("capacity", "Capacity", min_value=1, max_value=32767),
        form.text("lab_type", "Lab type", max_len=50),
    )
    return form, data


def show_form(item, errors, is_new, status=200):
    return render_template("labs/form.html", item=item, errors=errors, is_new=is_new), status


@bp.route("/new", methods=["GET", "POST"])
def create():
    if request.method == "GET":
        return show_form({}, {}, True)
    form, data = read_form()
    if not form.ok:
        return show_form(request.form, form.errors, True, 400)
    message = try_db(lambda: db.execute(
        "INSERT INTO lab (lab_name, location, capacity, lab_type) VALUES (%s, %s, %s, %s)", data))
    if message:
        flash(message, "error")
        return show_form(request.form, {}, True, 400)
    flash(f"Laboratory {data[0]} added.", "success")
    return redirect(url_for("labs.list_labs"))


@bp.route("/<int:lab_id>/edit", methods=["GET", "POST"])
def edit(lab_id):
    item = db.query_one("SELECT * FROM lab WHERE lab_id = %s", (lab_id,))
    if item is None:
        abort(404, "Laboratory not found.")
    if request.method == "GET":
        return show_form(item, {}, False)
    form, data = read_form()
    if not form.ok:
        return show_form(request.form, form.errors, False, 400)
    message = try_db(lambda: db.execute(
        "UPDATE lab SET lab_name = %s, location = %s, capacity = %s, lab_type = %s "
        "WHERE lab_id = %s", (*data, lab_id)))
    if message:
        flash(message, "error")
        return show_form(request.form, {}, False, 400)
    flash("Laboratory updated.", "success")
    return redirect(url_for("labs.list_labs"))


@bp.route("/<int:lab_id>/delete", methods=["POST"])
def delete(lab_id):
    message = try_db(lambda: db.execute("DELETE FROM lab WHERE lab_id = %s", (lab_id,)))
    flash(message or "Laboratory deleted.", "error" if message else "success")
    return redirect(url_for("labs.list_labs"))
