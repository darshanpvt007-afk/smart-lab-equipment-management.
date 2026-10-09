"""Reports: the important SQL queries from Review 2, run through the app.

Each report shows its SQL text next to the result so it can be explained
during the demonstration. "%s" is replaced by the application's date
(today, or the fixed reference date) as a query parameter.
"""
from flask import Blueprint, abort, render_template

from .. import db, today

bp = Blueprint("reports", __name__, url_prefix="/reports")

REPORTS = [
    {
        "slug": "overdue",
        "title": "Overdue allocations",
        "concept": "View + WHERE + date function (Q53)",
        "sql": """SELECT allocation_id, student_name, register_number, serial_number,
       expected_return_date, DATEDIFF(%s, expected_return_date) AS days_overdue
FROM   vw_outstanding_allocations
WHERE  expected_return_date < %s
ORDER  BY days_overdue DESC""",
        "params": 2,
    },
    {
        "slug": "equipment-per-lab",
        "title": "Equipment per laboratory",
        "concept": "JOIN + GROUP BY + COUNT / conditional SUM (Q16, Q51)",
        "sql": """SELECT l.lab_name,
       COUNT(e.equipment_id)                  AS total_items,
       SUM(e.availability_status = 'Available') AS available,
       SUM(e.availability_status = 'Allocated') AS allocated
FROM   lab l
LEFT JOIN equipment e ON e.lab_id = l.lab_id
GROUP  BY l.lab_id, l.lab_name
ORDER  BY total_items DESC, l.lab_name""",
        "params": 0,
    },
    {
        "slug": "supplier-spend",
        "title": "Expenditure per supplier (received purchases)",
        "concept": "WHERE before GROUP BY + SUM + COUNT (Q19)",
        "sql": """SELECT s.supplier_name,
       COUNT(p.purchase_id) AS purchases_received,
       SUM(p.total_amount)  AS total_expenditure
FROM   supplier s
JOIN   purchase p ON p.supplier_id = s.supplier_id
WHERE  p.purchase_status = 'Received'
GROUP  BY s.supplier_id, s.supplier_name
ORDER  BY total_expenditure DESC""",
        "params": 0,
    },
    {
        "slug": "maintenance-cost",
        "title": "Maintenance cost by type",
        "concept": "AVG / MIN / MAX / SUM, NULL handling (Q20)",
        "sql": """SELECT maintenance_type,
       COUNT(*)                        AS total_jobs,
       COUNT(maintenance_cost)         AS jobs_with_cost,
       ROUND(AVG(maintenance_cost), 2) AS average_cost,
       MIN(maintenance_cost)           AS minimum_cost,
       MAX(maintenance_cost)           AS maximum_cost,
       SUM(maintenance_cost)           AS total_cost
FROM   maintenance
GROUP  BY maintenance_type
ORDER  BY maintenance_type""",
        "params": 0,
    },
    {
        "slug": "frequent-borrowers",
        "title": "Students borrowing more than the average",
        "concept": "GROUP BY + HAVING compared with a subquery (Q47)",
        "sql": """SELECT s.register_number, s.student_name, COUNT(*) AS allocation_count
FROM   student s
JOIN   equipment_allocation a ON a.student_id = s.student_id
GROUP  BY s.student_id, s.register_number, s.student_name
HAVING COUNT(*) > (SELECT COUNT(*) FROM equipment_allocation)
                / (SELECT COUNT(*) FROM student)
ORDER  BY allocation_count DESC, s.student_name""",
        "params": 0,
    },
    {
        "slug": "never-maintained",
        "title": "Equipment never maintained",
        "concept": "Correlated NOT EXISTS subquery (Q44)",
        "sql": """SELECT e.serial_number, e.equipment_name, e.availability_status
FROM   equipment e
WHERE  NOT EXISTS (SELECT 1 FROM maintenance m
                   WHERE  m.equipment_id = e.equipment_id)
ORDER  BY e.serial_number""",
        "params": 0,
    },
    {
        "slug": "late-returns",
        "title": "Late returns",
        "concept": "Multi-table JOIN with a cross-table comparison (Q37)",
        "sql": """SELECT a.allocation_id, s.student_name, e.serial_number,
       a.expected_return_date, r.return_date,
       DATEDIFF(r.return_date, a.expected_return_date) AS days_late
FROM   equipment_allocation a
JOIN   equipment_return r ON r.allocation_id = a.allocation_id
JOIN   student          s ON s.student_id    = a.student_id
JOIN   equipment        e ON e.equipment_id  = a.equipment_id
WHERE  r.return_date > a.expected_return_date
ORDER  BY days_late DESC""",
        "params": 0,
    },
    {
        "slug": "costly-maintenance",
        "title": "Jobs costing more than their type's average",
        "concept": "Correlated subquery (Q45)",
        "sql": """SELECT m.maintenance_id, e.serial_number, m.maintenance_type, m.maintenance_cost
FROM   maintenance m
JOIN   equipment e ON e.equipment_id = m.equipment_id
WHERE  m.maintenance_cost > (SELECT AVG(m2.maintenance_cost)
                             FROM   maintenance m2
                             WHERE  m2.maintenance_type = m.maintenance_type)
ORDER  BY m.maintenance_type, m.maintenance_cost DESC""",
        "params": 0,
    },
]
BY_SLUG = {r["slug"]: r for r in REPORTS}


@bp.route("/")
def index():
    return render_template("reports/index.html", reports=REPORTS)


@bp.route("/<slug>")
def show(slug):
    report = BY_SLUG.get(slug)
    if report is None:
        abort(404, "Report not found.")
    rows = db.query_all(report["sql"], (today(),) * report["params"])
    columns = list(rows[0].keys()) if rows else []
    return render_template("reports/show.html", report=report, rows=rows, columns=columns)
