"""Equipment events: one timeline built from the tables that already record
what happened to each item (no extra audit table is needed).

  received      purchase.purchase_date           (the item arrived)
  issued        equipment_allocation.allocation_date
  returned      equipment_return.return_date
  maint-*       maintenance.maintenance_date     (scheduled / in-progress / completed)

The dashboard feed, the "Last activity" column of the equipment list and the
lifecycle on the equipment page all read from EVENTS_SQL. It is a fixed
string (no user input), so it can safely be used as a derived table.
"""
from . import db

# seq orders events that share a date: received < issued < returned < maintenance.
EVENTS_SQL = """
    SELECT e.equipment_id, p.purchase_date AS event_date, 0 AS seq, 'received' AS kind,
           p.purchase_id AS ref_id, sup.supplier_name AS person, NULL AS staff,
           p.invoice_number AS detail, NULL AS cost, NULL AS note
    FROM equipment e
    JOIN purchase p   ON p.purchase_id = e.purchase_id
    JOIN supplier sup ON sup.supplier_id = p.supplier_id
    UNION ALL
    SELECT a.equipment_id, a.allocation_date, 1, 'issued', a.allocation_id, s.student_name,
           ls.staff_name, a.expected_return_date, NULL, NULL
    FROM equipment_allocation a
    JOIN student s    ON s.student_id = a.student_id
    JOIN lab_staff ls ON ls.staff_id = a.staff_id
    UNION ALL
    SELECT a.equipment_id, r.return_date, 2, 'returned', a.allocation_id, s.student_name,
           NULL, r.return_condition, NULL, r.remarks
    FROM equipment_return r
    JOIN equipment_allocation a ON a.allocation_id = r.allocation_id
    JOIN student s              ON s.student_id = a.student_id
    UNION ALL
    SELECT m.equipment_id, m.maintenance_date, 3,
           CASE m.maintenance_status WHEN 'Completed' THEN 'maint-completed'
                                     WHEN 'In Progress' THEN 'maint-started'
                                     ELSE 'maint-scheduled' END,
           m.maintenance_id, NULL, ls.staff_name, m.maintenance_type, m.maintenance_cost, m.remarks
    FROM maintenance m
    JOIN lab_staff ls ON ls.staff_id = m.staff_id
"""

# The most recent event per item, ignoring jobs that are only planned.
LATEST_SQL = f"""
    SELECT * FROM (
        SELECT ev.*, ROW_NUMBER() OVER (PARTITION BY ev.equipment_id
                                        ORDER BY ev.event_date DESC, ev.seq DESC, ev.ref_id DESC) AS rn
        FROM ({EVENTS_SQL}) ev
        WHERE ev.kind <> 'maint-scheduled'
    ) ranked WHERE ranked.rn = 1
"""

MAINTENANCE_VERB = {"maint-completed": "completed", "maint-started": "started",
                    "maint-scheduled": "scheduled"}


def summary(ev):
    """Short sentence for an event, e.g. 'Issued to Kabir Nair'."""
    kind = ev["kind"]
    if kind == "received":
        return f"Received from {ev['person']}"
    if kind == "issued":
        return f"Issued to {ev['person']}"
    if kind == "returned":
        return f"Returned by {ev['person']}" + (" (damaged)" if ev["detail"] == "Damaged" else "")
    return f"{ev['detail']} {MAINTENANCE_VERB[kind]}"


def recent(on_or_before, limit=6):
    """Latest loans, returns and maintenance across all equipment (dashboard feed)."""
    return db.query_all(
        f"SELECT ev.*, e.equipment_name, e.serial_number FROM ({EVENTS_SQL}) ev "
        "JOIN equipment e ON e.equipment_id = ev.equipment_id "
        "WHERE ev.kind IN ('issued', 'returned', 'maint-started', 'maint-completed') "
        "  AND ev.event_date <= %s "
        "ORDER BY ev.event_date DESC, ev.seq DESC, ev.ref_id DESC LIMIT %s",
        (on_or_before, limit))


def for_equipment(equipment_id):
    """Full lifecycle of one item, newest first (planned jobs included)."""
    return db.query_all(
        f"SELECT ev.* FROM ({EVENTS_SQL}) ev WHERE ev.equipment_id = %s "
        "ORDER BY ev.event_date DESC, ev.seq DESC, ev.ref_id DESC", (equipment_id,))
