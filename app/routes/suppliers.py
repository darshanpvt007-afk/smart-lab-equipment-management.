"""Suppliers: list with purchase totals, add, edit, delete."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import db
from ..validators import Form
from . import try_db

bp = Blueprint("suppliers", __name__, url_prefix="/suppliers")


@bp.route("/")
def list_suppliers():
    rows = db.query_all(
        "SELECT s.supplier_id, s.supplier_name, s.contact_number, s.email, s.address, "
        "       COUNT(p.purchase_id) AS purchases, "
        "       SUM(CASE WHEN p.purchase_status = 'Received' THEN p.total_amount END) AS received_total "
        "FROM supplier s LEFT JOIN purchase p ON p.supplier_id = s.supplier_id "
        "GROUP BY s.supplier_id, s.supplier_name, s.contact_number, s.email, s.address "
        "ORDER BY s.supplier_name")
    return render_template("suppliers/list.html", rows=rows)


def read_form():
    form = Form(request.form)
    data = (
        form.text("supplier_name", "Supplier name", max_len=120),
        form.phone("contact_number"),
        form.email("email", required=False),
        form.text("address", "Address", required=False, max_len=255),
    )
    return form, data


def show_form(item, errors, is_new, status=200):
    return render_template("suppliers/form.html", item=item, errors=errors, is_new=is_new), status


@bp.route("/new", methods=["GET", "POST"])
def create():
    if request.method == "GET":
        return show_form({}, {}, True)
    form, data = read_form()
    if not form.ok:
        return show_form(request.form, form.errors, True, 400)
    message = try_db(lambda: db.execute(
        "INSERT INTO supplier (supplier_name, contact_number, email, address) VALUES (%s, %s, %s, %s)",
        data))
    if message:
        flash(message, "error")
        return show_form(request.form, {}, True, 400)
    flash(f"Supplier {data[0]} added.", "success")
    return redirect(url_for("suppliers.list_suppliers"))


@bp.route("/<int:supplier_id>/edit", methods=["GET", "POST"])
def edit(supplier_id):
    item = db.query_one("SELECT * FROM supplier WHERE supplier_id = %s", (supplier_id,))
    if item is None:
        abort(404, "Supplier not found.")
    if request.method == "GET":
        return show_form(item, {}, False)
    form, data = read_form()
    if not form.ok:
        return show_form(request.form, form.errors, False, 400)
    message = try_db(lambda: db.execute(
        "UPDATE supplier SET supplier_name = %s, contact_number = %s, email = %s, address = %s "
        "WHERE supplier_id = %s", (*data, supplier_id)))
    if message:
        flash(message, "error")
        return show_form(request.form, {}, False, 400)
    flash("Supplier updated.", "success")
    return redirect(url_for("suppliers.list_suppliers"))


@bp.route("/<int:supplier_id>/delete", methods=["POST"])
def delete(supplier_id):
    message = try_db(lambda: db.execute("DELETE FROM supplier WHERE supplier_id = %s", (supplier_id,)))
    flash(message or "Supplier deleted.", "error" if message else "success")
    return redirect(url_for("suppliers.list_suppliers"))
