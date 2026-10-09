"""Database access layer.

One MySQL connection per web request (stored in flask.g) and a few small
helpers. Every helper takes SQL with %s placeholders and a separate tuple
of values, so user input is always sent as data, never pasted into SQL
(this prevents SQL injection).
"""
import re

import mysql.connector
from flask import current_app, g


def get_db():
    if "db" not in g:
        cfg = current_app.config
        options = dict(user=cfg["DB_USER"], password=cfg["DB_PASSWORD"],
                       database=cfg["DB_NAME"], autocommit=False,
                       connection_timeout=cfg.get("DB_CONNECT_TIMEOUT", 5))
        if cfg.get("DB_SSL_CA"):
            # Hosted MySQL (e.g. Aiven): encrypt the connection and verify the
            # server certificate against the provider's CA file.
            options.update(ssl_ca=cfg["DB_SSL_CA"], ssl_verify_cert=True, ssl_verify_identity=True)
        if cfg.get("DB_UNIX_SOCKET"):
            options["unix_socket"] = cfg["DB_UNIX_SOCKET"]
        else:
            options.update(host=cfg["DB_HOST"], port=cfg["DB_PORT"])
        g.db = mysql.connector.connect(**options)
    return g.db


def close_db(_exc=None):
    """End of every request: undo anything not committed, then close.
    Even read-only requests hold a transaction snapshot until this point."""
    conn = g.pop("db", None)
    if conn is None:
        return
    try:
        conn.rollback()
    except mysql.connector.Error:
        pass                    # connection already broken; closing is all that is left
    finally:
        conn.close()


def init_app(app):
    app.teardown_appcontext(close_db)


def query_all(sql, params=()):
    """Run a SELECT and return a list of dict rows."""
    cur = get_db().cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        cur.close()


def query_one(sql, params=()):
    rows = query_all(sql, params)
    return rows[0] if rows else None


def execute(sql, params=()):
    """Run one INSERT / UPDATE / DELETE and commit it.
    Returns the new AUTO_INCREMENT id for an INSERT."""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        conn.commit()
        return cur.lastrowid
    except mysql.connector.Error:
        conn.rollback()
        raise
    finally:
        cur.close()


def call_procedure(name, args):
    """Call a stored procedure. The procedures manage their own transaction;
    the returned tuple contains the final values of OUT parameters."""
    conn = get_db()
    cur = conn.cursor()
    try:
        result = cur.callproc(name, args)
        conn.commit()
        return result
    except mysql.connector.Error:
        conn.rollback()
        raise
    finally:
        cur.close()


# ---------------------------------------------------------------------------
# Turning MySQL errors into messages a lab assistant can understand.
# ---------------------------------------------------------------------------
UNIQUE_MESSAGES = {
    "uq_student_register_no": "A student with this register number already exists.",
    "uq_app_user_username": "An account with this username already exists.",
    "uq_request_one_pending": "You already have a pending request for this item.",
    "uq_student_email": "A student with this e-mail address already exists.",
    "uq_lab_staff_email": "A staff member with this e-mail address already exists.",
    "uq_equipment_serial_number": "Equipment with this serial number already exists.",
    "uq_purchase_supplier_invoice": "This supplier already has a purchase with this invoice number.",
    "uq_lab_name": "A laboratory with this name already exists.",
    "uq_category_name": "A category with this name already exists.",
    "uq_supplier_name": "A supplier with this name already exists.",
    "uq_return_allocation": "This allocation has already been returned.",
    "uq_allocation_one_active_per_equipment": "This equipment is already issued to someone.",
}

CHECK_MESSAGES = {
    "chk_student_year": "Year of study must be between 1 and 5.",
    "chk_student_register_no": "Register number must look like 24BCE1012.",
    "chk_lab_capacity": "Capacity must be greater than 0.",
    "chk_purchase_amount": "Total amount must be greater than 0.",
    "chk_allocation_dates": "Expected return date must be on or after the allocation date.",
    "chk_equipment_damaged_not_available": "Damaged equipment cannot be marked Available.",
    "chk_maintenance_completed_cost": "A completed maintenance job needs a cost.",
}


def friendly_error(err):
    """Return a user-facing message for an expected database error,
    or None if the error is unexpected (it is then re-raised)."""
    code, text = err.errno, err.msg or ""
    if code == 1062:
        for key, message in UNIQUE_MESSAGES.items():
            if key in text:
                return message
        return "This value already exists and must be unique."
    if code == 1451:
        return ("This record cannot be deleted because other records refer to it "
                "(for example allocation, purchase or maintenance history).")
    if code == 1452:
        return "A selected related record does not exist any more. Please reload the form."
    if code == 1048:
        return "A required value is missing."
    if code == 3819:
        match = re.search(r"'(\w+)'", text)
        name = match.group(1) if match else ""
        return CHECK_MESSAGES.get(name, f"The value breaks a database rule ({name}).")
    if code == 1644:          # SIGNAL from a stored procedure: already readable
        return text
    return None
