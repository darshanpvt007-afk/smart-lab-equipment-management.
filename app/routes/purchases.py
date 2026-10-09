"""Purchases: list, add, edit, delete.

Extra rule checked here (also audited by V14): a purchase that already has
equipment linked to it must stay 'Received'.
"""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import db, today
from ..validators import PURCHASE_STATUSES, Form
from . import supplier_options, try_db

bp = Blueprint("purchases", __name__, url_prefix="/purchases")


@bp.route("/")
def list_purchases():
    rows = db.query_all(
        "SELECT p.purchase_id, p.purchase_date, p.invoice_number, p.total_amount, p.purchase_status, "
        "       s.supplier_name, COUNT(e.equipment_id) AS items "
        "FROM purchase p "
        "JOIN supplier s ON s.supplier_id = p.supplier_id "
        "LEFT JOIN equipment e ON e.purchase_id = p.purchase_id "
        "GROUP BY p.purchase_id, p.purchase_date, p.invoice_number, p.total_amount, "
        "         p.purchase_status, s.supplier_name "
        "ORDER BY p.purchase_date DESC")
    return render_template("purchases/list.html", rows=rows)


def read_form():
    form = Form(request.form)
    data = (
        form.integer("supplier_id", "Supplier"),
        form.date("purchase_date", "Purchase date", not_after=today()),
        form.text("invoice_number", "Invoice number", max_len=30, upper=True),
        form.money("total_amount", "Total amount", strictly_positive=True),
        form.choice("purchase_status", "Status", PURCHASE_STATUSES),
    )
    return form, data


def show_form(item, errors, is_new, status=200):
    return render_template("purchases/form.html", item=item, errors=errors, is_new=is_new,
                           suppliers=supplier_options(), statuses=PURCHASE_STATUSES), status


@bp.route("/new", methods=["GET", "POST"])
def create():
    if request.method == "GET":
        return show_form({"purchase_date": today().isoformat(), "purchase_status": "Ordered"}, {}, True)
    form, data = read_form()
    if not form.ok:
        return show_form(request.form, form.errors, True, 400)
    message = try_db(lambda: db.execute(
        "INSERT INTO purchase (supplier_id, purchase_date, invoice_number, total_amount, purchase_status) "
        "VALUES (%s, %s, %s, %s, %s)", data))
    if message:
        flash(message, "error")
        return show_form(request.form, {}, True, 400)
    flash(f"Purchase {data[2]} recorded.", "success")
    return redirect(url_for("purchases.list_purchases"))


@bp.route("/<int:purchase_id>/edit", methods=["GET", "POST"])
def edit(purchase_id):
    item = db.query_one("SELECT * FROM purchase WHERE purchase_id = %s", (purchase_id,))
    if item is None:
        abort(404, "Purchase not found.")
    if request.method == "GET":
        return show_form(item, {}, False)
    form, data = read_form()
    items = db.query_one("SELECT COUNT(*) AS n FROM equipment WHERE purchase_id = %s", (purchase_id,))["n"]
    if items and data[4] and data[4] != "Received":
        form.error("purchase_status",
                   f"{items} equipment item(s) already belong to this purchase, so it must stay Received.")
    if not form.ok:
        return show_form(request.form, form.errors, False, 400)
    message = try_db(lambda: db.execute(
        "UPDATE purchase SET supplier_id = %s, purchase_date = %s, invoice_number = %s, "
        "total_amount = %s, purchase_status = %s WHERE purchase_id = %s", (*data, purchase_id)))
    if message:
        flash(message, "error")
        return show_form(request.form, {}, False, 400)
    flash("Purchase updated.", "success")
    return redirect(url_for("purchases.list_purchases"))


@bp.route("/<int:purchase_id>/delete", methods=["POST"])
def delete(purchase_id):
    message = try_db(lambda: db.execute("DELETE FROM purchase WHERE purchase_id = %s", (purchase_id,)))
    flash(message or "Purchase deleted.", "error" if message else "success")
    return redirect(url_for("purchases.list_purchases"))
