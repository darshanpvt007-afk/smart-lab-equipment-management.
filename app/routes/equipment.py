"""Equipment: search, detail with history, add, edit, delete.

Condition and availability are NOT edited on this form: they change only
through the allocation/return and maintenance workflows (stored procedures),
so the stored status can never contradict the history (DESIGN_DECISIONS D-08).
"""
import csv
import io

from flask import (Blueprint, Response, abort, flash, redirect, render_template, request,
                   url_for)

from .. import activity, db, today
from ..validators import AVAILABILITY_STATUSES, Form
from . import category_options, lab_options, received_purchase_options, try_db

bp = Blueprint("equipment", __name__, url_prefix="/equipment")

# Saved views (tabs above the table). Fixed SQL fragments, never user text.
VIEWS = {
    "all": ("All equipment", None),
    "available": ("Available", "e.availability_status = 'Available'"),
    "on_loan": ("On loan", "e.availability_status = 'Allocated'"),
    "attention": ("Needs attention", "e.availability_status IN ('Under Maintenance', 'Unavailable')"),
}

# Sortable columns: URL key -> ORDER BY expression (whitelist, so ?sort= can
# never inject SQL). Every order ends with the serial number to be stable.
SORTS = {
    "name": "e.equipment_name",
    "category": "c.category_name",
    "lab": "l.lab_name",
    "condition": "FIELD(e.equipment_condition, 'New', 'Good', 'Fair', 'Damaged')",
    "status": "FIELD(e.availability_status, 'Available', 'Allocated', 'Under Maintenance', 'Unavailable')",
    "activity": "la.event_date",
}
PAGE_SIZES = (10, 25, 50)

LIST_FROM = (
    "FROM equipment e "
    "JOIN equipment_category c ON c.category_id = e.category_id "
    "JOIN lab l ON l.lab_id = e.lab_id "
    "LEFT JOIN vw_outstanding_allocations o ON o.equipment_id = e.equipment_id "
    f"LEFT JOIN ({activity.LATEST_SQL}) la ON la.equipment_id = e.equipment_id "
    "LEFT JOIN (SELECT equipment_id, MAX(maintenance_id) AS job_id FROM maintenance "
    "           WHERE maintenance_status = 'In Progress' GROUP BY equipment_id) jp "
    "       ON jp.equipment_id = e.equipment_id "
    "LEFT JOIN (SELECT equipment_id, MIN(maintenance_id) AS job_id FROM maintenance "
    "           WHERE maintenance_status = 'Scheduled' GROUP BY equipment_id) js "
    "       ON js.equipment_id = e.equipment_id "
)


def read_filters(args):
    """Validated list filters from the query string."""
    view = args.get("view", "all")
    status = args.get("status", "")
    sort = args.get("sort", "name")
    per_page = args.get("per_page", "25")
    page = args.get("page", "1")
    return {
        "q": args.get("q", "").strip(),
        "lab_id": args.get("lab_id", "") if args.get("lab_id", "").isdigit() else "",
        "category_id": args.get("category_id", "") if args.get("category_id", "").isdigit() else "",
        "status": status if status in AVAILABILITY_STATUSES else "",
        "view": view if view in VIEWS else "all",
        "sort": sort if sort in SORTS else "name",
        "dir": "desc" if args.get("dir") == "desc" else "asc",
        "per_page": int(per_page) if per_page.isdigit() and int(per_page) in PAGE_SIZES else 25,
        "page": max(int(page), 1) if page.isdigit() else 1,
    }


def base_where(f):
    """WHERE pieces for search, lab, category and status (not the view tab)."""
    where, params = [], []
    if f["q"]:
        where.append("(e.equipment_name LIKE %s OR e.serial_number LIKE %s)")
        params += [f"%{f['q']}%", f"%{f['q']}%"]
    if f["lab_id"]:
        where.append("e.lab_id = %s")
        params.append(int(f["lab_id"]))
    if f["category_id"]:
        where.append("e.category_id = %s")
        params.append(int(f["category_id"]))
    if f["status"]:
        where.append("e.availability_status = %s")
        params.append(f["status"])
    return where, params


def query_rows(f, paged=True):
    where, params = base_where(f)
    view_sql = VIEWS[f["view"]][1]
    if view_sql:
        where.append(view_sql)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    total = db.query_one("SELECT COUNT(*) AS n " + LIST_FROM + where_sql, params)["n"]
    direction = "DESC" if f["dir"] == "desc" else "ASC"
    sql = ("SELECT e.equipment_id, e.equipment_name, e.serial_number, e.equipment_condition, "
           "       e.availability_status, c.category_name, l.lab_name, "
           "       o.allocation_id, o.student_name AS holder, o.expected_return_date, "
           "       la.kind AS last_kind, la.event_date AS last_date, la.person AS last_person, "
           "       la.detail AS last_detail, jp.job_id AS job_in_progress, js.job_id AS job_scheduled "
           + LIST_FROM + where_sql +
           f" ORDER BY {SORTS[f['sort']]} {direction}, e.equipment_name, e.serial_number")
    if paged:
        sql += " LIMIT %s OFFSET %s"
        params = params + [f["per_page"], (f["page"] - 1) * f["per_page"]]
    rows = db.query_all(sql, params)
    for r in rows:
        r["overdue"] = r["expected_return_date"] is not None and r["expected_return_date"] < today()
        r["last_activity"] = activity.summary({"kind": r["last_kind"], "person": r["last_person"],
                                               "detail": r["last_detail"]}) if r["last_kind"] else None
    return rows, total


@bp.route("/")
def list_equipment():
    f = read_filters(request.args)
    rows, total = query_rows(f)
    pages = max((total + f["per_page"] - 1) // f["per_page"], 1)
    if f["page"] > pages:                       # e.g. page 3 after narrowing the search
        f["page"] = pages
        rows, total = query_rows(f)

    # Tab counts honour the search/lab/category/status filters, not the tab itself.
    where, params = base_where(f)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    by_status = {r["availability_status"]: r["n"] for r in db.query_all(
        "SELECT e.availability_status, COUNT(*) AS n FROM equipment e" + where_sql +
        " GROUP BY e.availability_status", params)}
    view_counts = {
        "all": sum(by_status.values()),
        "available": by_status.get("Available", 0),
        "on_loan": by_status.get("Allocated", 0),
        "attention": by_status.get("Under Maintenance", 0) + by_status.get("Unavailable", 0),
    }

    return render_template("equipment/list.html", rows=rows, total=total, pages=pages,
                           list_url=lambda endpoint="equipment.list_equipment", **changes:
                               list_url(f, endpoint, **changes),
                           filters=f, views=VIEWS, view_counts=view_counts, page_sizes=PAGE_SIZES,
                           labs=lab_options(), categories=category_options(),
                           statuses=AVAILABILITY_STATUSES)


LIST_DEFAULTS = {"q": "", "lab_id": "", "category_id": "", "status": "", "view": "all",
                 "sort": "name", "dir": "asc", "per_page": 25, "page": 1}


def list_url(f, endpoint, **changes):
    """URL of the list with the current filters plus `changes` (defaults left out)."""
    merged = dict(f, **changes)
    params = {k: v for k, v in merged.items() if k in LIST_DEFAULTS and v != LIST_DEFAULTS[k]}
    return url_for(endpoint, **params)


def csv_safe(value):
    """Stop spreadsheet formula injection: a cell must not start with = + - @."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


@bp.route("/export.csv")
def export_csv():
    """The current list (same filters and order, all pages) as a CSV download."""
    f = read_filters(request.args)
    rows, _ = query_rows(f, paged=False)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Serial number", "Equipment", "Category", "Laboratory", "Condition",
                     "Availability", "Held by", "Due", "Last activity", "Last activity date"])
    for r in rows:
        writer.writerow([csv_safe(v) for v in (
            r["serial_number"], r["equipment_name"], r["category_name"], r["lab_name"],
            r["equipment_condition"], r["availability_status"], r["holder"],
            r["expected_return_date"], r["last_activity"], r["last_date"])])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=equipment-{today().isoformat()}.csv"})


DETAIL_TABS = ("overview", "loans", "maintenance")


@bp.route("/<int:equipment_id>")
def detail(equipment_id):
    item = db.query_one("SELECT * FROM vw_equipment_inventory WHERE equipment_id = %s", (equipment_id,))
    if item is None:
        abort(404, "Equipment not found.")
    tab = request.args.get("tab", "overview")
    if tab not in DETAIL_TABS:
        tab = "overview"
    allocations = db.query_all(
        "SELECT * FROM vw_allocation_history WHERE serial_number = %s "
        "ORDER BY allocation_date DESC, allocation_id DESC", (item["serial_number"],))
    jobs = db.query_all(
        "SELECT * FROM vw_maintenance_history WHERE equipment_id = %s "
        "ORDER BY maintenance_date DESC, maintenance_id DESC", (equipment_id,))
    current = db.query_one(
        "SELECT o.*, s.department, DATEDIFF(%s, o.expected_return_date) AS days_overdue "
        "FROM vw_outstanding_allocations o JOIN student s ON s.student_id = o.student_id "
        "WHERE o.equipment_id = %s", (today(), equipment_id))
    events = activity.for_equipment(equipment_id)
    open_job = next((j for j in jobs if j["maintenance_status"] == "In Progress"), None) or \
        next((j for j in reversed(jobs) if j["maintenance_status"] == "Scheduled"), None)
    spent = sum(j["maintenance_cost"] for j in jobs
                if j["maintenance_status"] == "Completed" and j["maintenance_cost"] is not None)
    return render_template("equipment/detail.html", item=item, allocations=allocations, jobs=jobs,
                           current=current, events=events, open_job=open_job, spent=spent, tab=tab)


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
