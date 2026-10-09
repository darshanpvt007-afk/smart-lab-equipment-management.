"""Equipment categories: list with item counts, add, edit, delete."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import db
from ..validators import Form
from . import try_db

bp = Blueprint("categories", __name__, url_prefix="/categories")


@bp.route("/")
def list_categories():
    rows = db.query_all(
        "SELECT c.category_id, c.category_name, c.description, COUNT(e.equipment_id) AS equipment_count "
        "FROM equipment_category c LEFT JOIN equipment e ON e.category_id = c.category_id "
        "GROUP BY c.category_id, c.category_name, c.description ORDER BY c.category_name")
    return render_template("categories/list.html", rows=rows)


def read_form():
    form = Form(request.form)
    data = (
        form.text("category_name", "Category name", max_len=80),
        form.text("description", "Description", required=False, max_len=255),
    )
    return form, data


def show_form(item, errors, is_new, status=200):
    return render_template("categories/form.html", item=item, errors=errors, is_new=is_new), status


@bp.route("/new", methods=["GET", "POST"])
def create():
    if request.method == "GET":
        return show_form({}, {}, True)
    form, data = read_form()
    if not form.ok:
        return show_form(request.form, form.errors, True, 400)
    message = try_db(lambda: db.execute(
        "INSERT INTO equipment_category (category_name, description) VALUES (%s, %s)", data))
    if message:
        flash(message, "error")
        return show_form(request.form, {}, True, 400)
    flash(f"Category {data[0]} added.", "success")
    return redirect(url_for("categories.list_categories"))


@bp.route("/<int:category_id>/edit", methods=["GET", "POST"])
def edit(category_id):
    item = db.query_one("SELECT * FROM equipment_category WHERE category_id = %s", (category_id,))
    if item is None:
        abort(404, "Category not found.")
    if request.method == "GET":
        return show_form(item, {}, False)
    form, data = read_form()
    if not form.ok:
        return show_form(request.form, form.errors, False, 400)
    message = try_db(lambda: db.execute(
        "UPDATE equipment_category SET category_name = %s, description = %s WHERE category_id = %s",
        (*data, category_id)))
    if message:
        flash(message, "error")
        return show_form(request.form, {}, False, 400)
    flash("Category updated.", "success")
    return redirect(url_for("categories.list_categories"))


@bp.route("/<int:category_id>/delete", methods=["POST"])
def delete(category_id):
    message = try_db(lambda: db.execute(
        "DELETE FROM equipment_category WHERE category_id = %s", (category_id,)))
    flash(message or "Category deleted.", "error" if message else "success")
    return redirect(url_for("categories.list_categories"))
