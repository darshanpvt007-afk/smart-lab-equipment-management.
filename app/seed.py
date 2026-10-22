"""Ready-made sign-in accounts for the team, the lab teachers and the sample
students (command: flask seed-accounts, docs/DEPLOYMENT.md section 10.4).

Only usernames and roles are written here. Passwords are generated when the
command runs, stored in the database as scrypt hashes, and written once to a
private file (permissions 600) on the machine that runs the command. They are
never printed, logged or committed.
"""
import csv
import os
import secrets

from . import auth, db

# (username, full name, role, lab_staff email or None)
STAFF_ACCOUNTS = [
    ("darshan.s", "Darshan S", "admin", None),
    ("abishek.raj", "Abishek Raj", "admin", None),
    ("chaitanya.kumar", "Chaitanya Kumar", "admin", None),
    # lab teachers, linked to their lab_staff rows in the sample data
    ("kavitha.ramesh", "Kavitha Ramesh", "lab_manager", "kavitha.ramesh@staff.example.edu"),
    ("priya.sundaram", "Priya Sundaram", "lab_manager", "priya.sundaram@staff.example.edu"),
    ("ramesh.kumar", "Ramesh Kumar", "lab_manager", "ramesh.kumar@staff.example.edu"),
]

# No 0/O, 1/l/I: easy to read aloud and type.
_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_password(username=""):
    """Three groups of four, e.g. Kq7m-Xp2r-Wn4t (about 71 bits of randomness)."""
    while True:
        password = "-".join("".join(secrets.choice(_ALPHABET) for _ in range(4)) for _ in range(3))
        if auth.password_problem(password, username) is None:
            return password


def _open_private(path):
    """Create the credentials file readable by the owner only; never overwrite."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    return os.fdopen(fd, "w", newline="", encoding="utf-8")


def seed_accounts(out_path, reset=False):
    """Create the staff and student accounts. Existing accounts are left alone
    unless reset=True, which gives them a new password (and signs them out).
    Returns a list of (kind, login, name, role, action) rows, without passwords."""
    staff_rows = []
    for username, name, role, email in STAFF_ACCOUNTS:
        staff = db.query_one("SELECT staff_id FROM lab_staff WHERE email = %s", (email,)) if email else None
        existing = db.query_one("SELECT user_id FROM app_user WHERE username = %s", (username,))
        staff_rows.append((username, name, role, staff["staff_id"] if staff else None, existing))

    # A pending account (activation opened, no password yet) still needs a password.
    students = db.query_all("SELECT s.student_id, s.student_name, s.register_number, "
                        "       a.student_id IS NOT NULL AS has_account, "
                        "       a.password_hash IS NOT NULL AS has_password "
                        "FROM student s LEFT JOIN student_account a ON a.student_id = s.student_id "
                        "ORDER BY s.register_number")

    planned = [r for r in staff_rows if reset or not r[4]] + [s for s in students if reset or not s["has_password"]]
    summary = []
    if not planned:
        for username, name, role, _, _ in staff_rows:
            summary.append(("staff", username, name, auth.ROLES[role], "kept"))
        for s in students:
            summary.append(("student", s["register_number"], s["student_name"], "Student", "kept"))
        return summary

    with _open_private(out_path) as fh:
        out = csv.writer(fh)
        out.writerow(["type", "sign_in_name", "full_name", "role", "password"])
        for username, name, role, staff_id, existing in staff_rows:
            if existing and not reset:
                summary.append(("staff", username, name, auth.ROLES[role], "kept"))
                continue
            password = generate_password(username)
            if existing:
                db.execute("UPDATE app_user SET password_hash = %s, role = %s, staff_id = %s, is_active = TRUE, "
                           "session_epoch = session_epoch + 1 WHERE user_id = %s",
                           (auth.hash_password(password), role, staff_id, existing["user_id"]))
                action = "password reset"
            else:
                auth.insert_user(username, role, password, staff_id)
                action = "created"
            out.writerow(["staff", username, name, auth.ROLES[role], password])
            summary.append(("staff", username, name, auth.ROLES[role], action))

        for s in students:
            if s["has_password"] and not reset:
                summary.append(("student", s["register_number"], s["student_name"], "Student", "kept"))
                continue
            password = generate_password(s["register_number"])
            hashed = auth.hash_password(password)
            db.execute(
                "INSERT INTO student_account (student_id, password_hash, activated_at) VALUES (%s, %s, NOW()) "
                "ON DUPLICATE KEY UPDATE password_hash = %s, is_active = TRUE, "
                "  activated_at = NOW(), activation_expires_at = NULL, session_epoch = session_epoch + 1",
                (s["student_id"], hashed, hashed))
            out.writerow(["student", s["register_number"], s["student_name"], "Student", password])
            action = ("password reset" if s["has_password"] else
                      "activated" if s["has_account"] else "created")
            summary.append(("student", s["register_number"], s["student_name"], "Student", action))
    return summary
