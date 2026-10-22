"""TA93-TA96: `flask seed-accounts` creates the ready-made team, lab-teacher
and student accounts with generated passwords that only reach a private file.
"""
import csv
import os
import stat
from pathlib import Path

import pytest
from conftest import Client

from app import seed


def run(app, *args):
    return app.test_cli_runner().invoke(args=["seed-accounts", *args])


def read_credentials(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return {row["sign_in_name"]: row for row in csv.DictReader(fh)}


def sign_in(app, name, password):
    return Client(app.test_client()).post("/login", {"username": name, "password": password})


@pytest.fixture
def seeded(app, tmp_path):
    out = tmp_path / "credentials.csv"
    result = run(app, "--out", str(out))
    assert result.exit_code == 0, result.output
    return out, result.output


def test_ta93_creates_all_accounts_and_a_private_file(seeded, sql):
    out, output = seeded
    creds = read_credentials(out)
    assert stat.S_IMODE(os.stat(out).st_mode) == 0o600
    assert len(creds) == 16                                   # 6 staff + 10 sample students
    users = {r["username"]: r for r in sql("SELECT username, role, staff_id FROM app_user")}
    assert {u for u, r in users.items() if r["role"] == "admin"} == {"darshan.s", "abishek.raj", "chaitanya.kumar"}
    teachers = {u: r["staff_id"] for u, r in users.items() if r["role"] == "lab_manager"}
    assert teachers == {"kavitha.ramesh": 4, "priya.sundaram": 2, "ramesh.kumar": 1}
    assert sql("SELECT COUNT(*) AS n FROM student_account WHERE password_hash IS NOT NULL "
               "AND activation_expires_at IS NULL AND is_active")[0]["n"] == 10
    for row in creds.values():                                # passwords only in the file
        assert row["password"] not in output
        assert len(row["password"]) == 14 and row["password"].count("-") == 2
    hashes = " ".join(r["password_hash"] for r in sql("SELECT password_hash FROM app_user"))
    assert all(row["password"] not in hashes for row in creds.values())


def test_ta94_generated_passwords_sign_in(app, seeded):
    creds = read_credentials(seeded[0])
    for name, home in (("darshan.s", "/"), ("kavitha.ramesh", "/"), ("24BCE1012", "/my/")):
        response = sign_in(app, name, creds[name]["password"])
        assert response.status_code == 302 and response.headers["Location"] == home, name
    assert sign_in(app, "abishek.raj", creds["darshan.s"]["password"]).status_code == 401


def test_ta95_rerun_keeps_accounts_and_refuses_unsafe_files(app, seeded, sql, tmp_path):
    before = sql("SELECT username, password_hash FROM app_user ORDER BY username")
    again = tmp_path / "again.csv"
    result = run(app, "--out", str(again))
    assert result.exit_code == 0 and "nothing changed" in result.output and not again.exists()
    assert sql("SELECT username, password_hash FROM app_user ORDER BY username") == before
    assert run(app, "--out", str(seeded[0])).exit_code != 0                      # never overwrites
    inside = Path(__file__).resolve().parents[2] / "credentials.csv"
    refused = run(app, "--out", str(inside))
    assert refused.exit_code != 0 and "outside the project" in refused.output and not inside.exists()


def test_ta96_reset_gives_new_passwords_and_signs_out(app, seeded, sql, tmp_path):
    old = read_credentials(seeded[0])
    epoch = sql("SELECT session_epoch FROM app_user WHERE username = 'darshan.s'")[0]["session_epoch"]
    out = tmp_path / "reset.csv"
    assert run(app, "--reset", "--out", str(out)).exit_code == 0
    new = read_credentials(out)
    assert new["darshan.s"]["password"] != old["darshan.s"]["password"]
    assert sql("SELECT session_epoch FROM app_user WHERE username = 'darshan.s'")[0]["session_epoch"] == epoch + 1
    assert sign_in(app, "darshan.s", old["darshan.s"]["password"]).status_code == 401
    assert sign_in(app, "24BCE1012", new["24BCE1012"]["password"]).status_code == 302


def test_generated_passwords_pass_the_password_rules():
    from app import auth
    for _ in range(200):
        assert auth.password_problem(seed.generate_password("darshan.s"), "darshan.s") is None
