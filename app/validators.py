"""Server-side input validation.

The rules mirror the database constraints (sql/02_create_tables.sql) so
that the user gets a clear message next to the field *before* the data
reaches MySQL. The database still enforces every rule as the final guard.

Usage:
    form = Form(request.form)
    name = form.text("student_name", "Name", max_len=100)
    year = form.integer("year_of_study", "Year", min_value=1, max_value=5)
    if form.ok: ...save... else: show form.errors
"""
import re
from datetime import date
from decimal import Decimal, InvalidOperation

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[0-9]{10,14}$")
REGISTER_RE = re.compile(r"^[0-9]{2}[A-Z]{3}[0-9]{4}$")      # e.g. 24BCE1012

EQUIPMENT_CONDITIONS = ("New", "Good", "Fair", "Damaged")
RETURN_CONDITIONS = ("Good", "Fair", "Damaged")
AVAILABILITY_STATUSES = ("Available", "Allocated", "Under Maintenance", "Unavailable")
MAINTENANCE_TYPES = ("Preventive", "Repair", "Calibration")
MAINTENANCE_STATUSES = ("Scheduled", "In Progress", "Completed")
PURCHASE_STATUSES = ("Ordered", "Received", "Cancelled")


class Form:
    def __init__(self, data):
        self.data = data
        self.errors = {}

    @property
    def ok(self):
        return not self.errors

    def error(self, field, message):
        self.errors.setdefault(field, message)

    def _raw(self, field):
        return (self.data.get(field) or "").strip()

    def text(self, field, label, required=True, max_len=255, pattern=None,
             pattern_message=None, upper=False):
        value = self._raw(field)
        if upper:
            value = value.upper()
        if not value:
            if required:
                self.error(field, f"{label} is required.")
            return None
        if len(value) > max_len:
            self.error(field, f"{label} must be at most {max_len} characters.")
        elif pattern is not None and not pattern.match(value):
            self.error(field, pattern_message or f"{label} has an invalid format.")
        return value

    def email(self, field, label="E-mail", required=True):
        return self.text(field, label, required, 120, EMAIL_RE,
                         f"{label} must look like name@example.com.")

    def phone(self, field, label="Contact number"):
        return self.text(field, label, True, 15, PHONE_RE,
                         f"{label} must be 10-14 digits (an optional leading + is allowed).")

    def integer(self, field, label, required=True, min_value=None, max_value=None):
        raw = self._raw(field)
        if not raw:
            if required:
                self.error(field, f"{label} is required.")
            return None
        try:
            value = int(raw)
        except ValueError:
            self.error(field, f"{label} must be a whole number.")
            return None
        if min_value is not None and value < min_value:
            self.error(field, f"{label} must be at least {min_value}.")
        if max_value is not None and value > max_value:
            self.error(field, f"{label} must be at most {max_value}.")
        return value

    def money(self, field, label, required=True, min_value=Decimal("0"), strictly_positive=False):
        raw = self._raw(field)
        if not raw:
            if required:
                self.error(field, f"{label} is required.")
            return None
        try:
            value = Decimal(raw)
        except InvalidOperation:
            self.error(field, f"{label} must be a number such as 1250.00.")
            return None
        if not value.is_finite():
            self.error(field, f"{label} must be a number such as 1250.00.")
        elif value.as_tuple().exponent < -2:
            self.error(field, f"{label} can have at most 2 decimal places.")
        elif strictly_positive and value <= 0:
            self.error(field, f"{label} must be greater than 0.")
        elif value < min_value:
            self.error(field, f"{label} cannot be negative.")
        elif value >= Decimal("10000000000"):
            self.error(field, f"{label} is too large.")
        return value

    def date(self, field, label, required=True, not_after=None, not_before=None):
        raw = self._raw(field)
        if not raw:
            if required:
                self.error(field, f"{label} is required.")
            return None
        try:
            value = date.fromisoformat(raw)
        except ValueError:
            self.error(field, f"{label} must be a valid date (YYYY-MM-DD).")
            return None
        if not_after is not None and value > not_after:
            self.error(field, f"{label} cannot be after {not_after.isoformat()}.")
        if not_before is not None and value < not_before:
            self.error(field, f"{label} cannot be before {not_before.isoformat()}.")
        return value

    def choice(self, field, label, choices, required=True):
        value = self._raw(field)
        if not value:
            if required:
                self.error(field, f"{label} is required.")
            return None
        if value not in choices:
            self.error(field, f"{label} must be one of: {', '.join(choices)}.")
            return None
        return value
