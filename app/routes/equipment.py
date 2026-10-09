"""Equipment: search, detail with history, add, edit, delete.

Condition and availability are NOT edited on this form: they change only
through the allocation/return and maintenance workflows (stored procedures),
so the stored status can never contradict the history (DESIGN_DECISIONS D-08).
"""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import db
from ..validators import AVAILABILITY_STATUSES, Form
from . import category_options, lab_options, received_purchase_options, try_db

bp = Blueprint("equipment", __name__, url_prefix="/equipment")


@bp.route("/")
def list_equipment():
    q = request.args.get("q", "").strip()
    lab_id = request.args.get("lab_id", "")
    category_id = request.args.get("category_id", "")
    status = request.args.get("status", "")

    # Build the WHERE clause from fixed pieces; user values go in params only.
    where, params = [], []
    if q:
        where.append("(e.equipment_name LIKE %s OR e.serial_number LIKE %s)")
        params += [f"%{q}%", f"%{q}%"]
    if lab_id.isdigit():
        where.append("e.lab_id = %s")
        params.append(int(lab_id))
    if category_id.isdigit():
        where.append("e.category_id = %s")
        params.append(int(category_id))
    if status in AVAILABILITY_STATUSES:
        where.append("e.availability_status = %s")
        params.append(status)

    sql = ("SELECT e.equipment_id, e.equipment_name, e.serial_number, e.equipment_condition, "
           "       e.availability_status, c.category_name, l.lab_name "
           "FROM equipment e "
           "JOIN equipment_category c ON c.category_id = e.category_id "
           "JOIN lab l ON l.lab_id = e.lab_id")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY e.equipment_name, e.serial_number"

    return render_template("equipment/list.html", rows=db.query_all(sql, params),
                           labs=lab_options(), categories=category_options(),
                           statuses=AVAILABILITY_STATUSES,
                           filters={"q": q, "lab_id": lab_id, "category_id": category_id, "status": status})


@bp.route("/<int:equipment_id>")
def detail(equipment_id):
    item = db.query_one("SELECT * FROM vw_equipment_inventory WHERE equipment_id = %s", (equipment_id,))
    if item is None:
        abort(404, "Equipment not found.")
    allocations = db.query_all(
        "SELECT * FROM vw_allocation_history WHERE serial_number = %s ORDER BY allocation_date DESC",
        (item["serial_number"],))
    jobs = db.query_all(
        "SELECT * FROM vw_maintenance_history WHERE equipment_id = %s ORDER BY maintenance_date DESC",
        (equipment_id,))
    return render_template("equipment/detail.html", item=item, allocations=allocations, jobs=jobs)


def read_form():
    form = Form(request.form)
    data = {
        "equipment_name": form.text("equipment_name", "Equipment name", max_len=120),
        "serial_number": form.text("serial_number", "Serial number", max_len=50, upper=True),
        "category_id": form.integer("category_id", "Category"),
        "lab_id": form.integer("lab_id", "Laboratory"),
        "purchase_id": form.integer("purchase_id", "Purchase"),
    }
    return form, data


def render_form(item, errors=None, is_new=True):
    return render_template("equipment/form.html", item=item, errors=errors or {}, is_new=is_new,
                           labs=lab_options(), categories=category_options(),
                           purchases=received_purchase_options(),
                           conditions=("New", "Good", "Fair"))


@bp.route("/new", methods=["GET", "POST"])
def create():
    if request.method == "GET":
        return render_form({"equipment_condition": "New"})
    form, data = read_form()
    data["equipment_condition"] = form.choice("equipment_condition", "Condition", ("New", "Good", "Fair"))
    if not form.ok:
        return render_form(request.form, form.errors), 400

    new_id = {}
    def insert():
        new_id["id"] = db.execute(
            "INSERT INTO equipment (equipment_name, serial_number, equipment_condition, "
            "availability_status, category_id, lab_id, purchase_id) "
            "VALUES (%s, %s, %s, 'Available', %s, %s, %s)",
            (data["equipment_name"], data["serial_number"], data["equipment_condition"],
             data["category_id"], data["lab_id"], data["purchase_id"]))
    message = try_db(insert)
    if message:
        flash(message, "error")
        return render_form(request.form), 400
    flash(f"Equipment {data['serial_number']} added.", "success")
    return redirect(url_for("equipment.detail", equipment_id=new_id["id"]))


@bp.route("/<int:equipment_id>/edit", methods=["GET", "POST"])
def edit(equipment_id):
    item = db.query_one("SELECT * FROM equipment WHERE equipment_id = %s", (equipment_id,))
    if item is None:
        abort(404, "Equipment not found.")
    if request.method == "GET":
        return render_form(item, is_new=False)
    form, data = read_form()
    if not form.ok:
        return render_form(request.form, form.errors, is_new=False), 400

    message = try_db(lambda: db.execute(
        "UPDATE equipment SET equipment_name = %s, serial_number = %s, category_id = %s, "
        "lab_id = %s, purchase_id = %s WHERE equipment_id = %s",
        (data["equipment_name"], data["serial_number"], data["category_id"],
         data["lab_id"], data["purchase_id"], equipment_id)))
    if message:
        flash(message, "error")
        return render_form(request.form, is_new=False), 400
    flash("Equipment updated.", "success")
    return redirect(url_for("equipment.detail", equipment_id=equipment_id))


@bp.route("/<int:equipment_id>/delete", methods=["POST"])
def delete(equipment_id):
    message = try_db(lambda: db.execute("DELETE FROM equipment WHERE equipment_id = %s", (equipment_id,)))
    if message:
        flash(message, "error")
        return redirect(url_for("equipment.detail", equipment_id=equipment_id))
    flash("Equipment deleted.", "success")
    return redirect(url_for("equipment.list_equipment"))
