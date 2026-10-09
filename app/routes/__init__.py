"""Blueprints (one module per part of the system) and small shared helpers."""
import mysql.connector

from .. import db


def try_db(action):
    """Run a database write. Return None on success, or a friendly error
    message for expected errors (duplicate, foreign key, CHECK, procedure
    refusal). Unexpected errors are re-raised and shown as a 500 page."""
    try:
        action()
        return None
    except mysql.connector.Error as err:
        message = db.friendly_error(err)
        if message is None:
            raise
        return message


# Option lists for <select> elements ------------------------------------------
def lab_options():
    return db.query_all("SELECT lab_id AS id, lab_name AS name FROM lab ORDER BY lab_name")


def category_options():
    return db.query_all("SELECT category_id AS id, category_name AS name "
                        "FROM equipment_category ORDER BY category_name")


def supplier_options():
    return db.query_all("SELECT supplier_id AS id, supplier_name AS name FROM supplier ORDER BY supplier_name")


def received_purchase_options():
    return db.query_all(
        "SELECT p.purchase_id AS id, CONCAT(p.invoice_number, ' - ', s.supplier_name, "
        "' (', p.purchase_date, ')') AS name "
        "FROM purchase p JOIN supplier s ON s.supplier_id = p.supplier_id "
        "WHERE p.purchase_status = 'Received' ORDER BY p.purchase_date DESC")


def student_options():
    return db.query_all("SELECT student_id AS id, CONCAT(register_number, ' - ', student_name) AS name "
                        "FROM student ORDER BY register_number")


def staff_options():
    return db.query_all("SELECT staff_id AS id, CONCAT(staff_name, ' (', designation, ')') AS name "
                        "FROM lab_staff ORDER BY staff_name")


def equipment_options(available_only=False):
    sql = ("SELECT equipment_id AS id, CONCAT(serial_number, ' - ', equipment_name, "
           "' [', availability_status, ']') AS name FROM equipment")
    if available_only:
        sql += " WHERE availability_status = 'Available'"
    return db.query_all(sql + " ORDER BY equipment_name, serial_number")
