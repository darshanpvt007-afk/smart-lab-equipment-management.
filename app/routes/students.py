"""Students: search, detail with allocation history, add, edit, delete."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import db
from ..validators import REGISTER_RE, Form
from . import try_db

bp = Blueprint("students", __name__, url_prefix="/students")


@bp.route("/")
def list_students():
    q = request.args.get("q", "").strip()
    department = request.args.get("department", "").strip()
    year = request.args.get("year", "")

    where, params = [], []
    if q:
        where.append("(s.student_name LIKE %s OR s.register_number LIKE %s)")
        params += [f"%{q}%", f"%{q}%"]
    if department:
        where.append("s.department = %s")
        params.append(department)
    if year.isdigit():
        where.append("s.year_of_study = %s")
        params.append(int(year))

    sql = ("SELECT s.student_id, s.register_number, s.student_name, s.department, s.year_of_study, "
           "       s.email, COUNT(a.allocation_id) AS allocations, "
           "       SUM(a.allocation_status = 'Issued') AS holding "
           "FROM student s LEFT JOIN equipment_allocation a ON a.student_id = s.student_id")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += (" GROUP BY s.student_id, s.register_number, s.student_name, s.department, "
            "s.year_of_study, s.email ORDER BY s.register_number")

    departments = [r["department"] for r in
                   db.query_all("SELECT DISTINCT department FROM student ORDER BY department")]
    return render_template("students/list.html", rows=db.query_all(sql, params),
                           departments=departments,
                           filters={"q": q, "department": department, "year": year})


@bp.route("/<int:student_id>")
def detail(student_id):
    student = db.query_one("SELECT * FROM student WHERE student_id = %s", (student_id,))
    if student is None:
        abort(404, "Student not found.")
    history = db.query_all(
        "SELECT * FROM vw_allocation_history WHERE register_number = %s ORDER BY allocation_date DESC",
        (student["register_number"],))
    return render_template("students/detail.html", student=student, history=history)


def read_form():
    form = Form(request.form)
    data = (
        form.text("student_name", "Name", max_len=100),
        form.text("register_number", "Register number", max_len=15, pattern=REGISTER_RE,
                  pattern_message="Register number must look like 24BCE1012.", upper=True),
        form.text("department", "Department", max_len=60, upper=True),
        form.integer("year_of_study", "Year of study", min_value=1, max_value=5),
        form.email("email"),
    )
    return form, data


@bp.route("/new", methods=["GET", "POST"])
def create():
    if request.method == "GET":
        return render_template("students/form.html", item={}, errors={}, is_new=True)
    form, data = read_form()
    if not form.ok:
        return render_template("students/form.html", item=request.form, errors=form.errors, is_new=True), 400
    message = try_db(lambda: db.execute(
        "INSERT INTO student (student_name, register_number, department, year_of_study, email) "
        "VALUES (%s, %s, %s, %s, %s)", data))
    if message:
        flash(message, "error")
        return render_template("students/form.html", item=request.form, errors={}, is_new=True), 400
    flash(f"Student {data[1]} added.", "success")
    return redirect(url_for("students.list_students"))


@bp.route("/<int:student_id>/edit", methods=["GET", "POST"])
def edit(student_id):
    student = db.query_one("SELECT * FROM student WHERE student_id = %s", (student_id,))
    if student is None:
        abort(404, "Student not found.")
    if request.method == "GET":
        return render_template("students/form.html", item=student, errors={}, is_new=False)
    form, data = read_form()
    if not form.ok:
        return render_template("students/form.html", item=request.form, errors=form.errors, is_new=False), 400
    message = try_db(lambda: db.execute(
        "UPDATE student SET student_name = %s, register_number = %s, department = %s, "
        "year_of_study = %s, email = %s WHERE student_id = %s", (*data, student_id)))
    if message:
        flash(message, "error")
        return render_template("students/form.html", item=request.form, errors={}, is_new=False), 400
    flash("Student updated.", "success")
    return redirect(url_for("students.detail", student_id=student_id))


@bp.route("/<int:student_id>/delete", methods=["POST"])
def delete(student_id):
    message = try_db(lambda: db.execute("DELETE FROM student WHERE student_id = %s", (student_id,)))
    if message:
        flash(message, "error")
        return redirect(url_for("students.detail", student_id=student_id))
    flash("Student deleted.", "success")
    return redirect(url_for("students.list_students"))
