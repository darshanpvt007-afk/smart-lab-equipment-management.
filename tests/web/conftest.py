"""pytest fixtures for the web-application tests.

The tests never touch smart_lab_equipment_db. Before EVERY test the
database smart_lab_equipment_apptest is dropped and rebuilt from the
project's SQL files (01, 02, 03, 08, 11, 12), so each test starts from the
documented sample data and tests cannot affect each other.

Connection settings come from the same environment variables as the app
(DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_UNIX_SOCKET). The `mysql`
command-line client must be installed (it understands DELIMITER).
"""
import os
import subprocess
import tempfile
from pathlib import Path

import mysql.connector
import pytest

from app import create_app

ROOT = Path(__file__).resolve().parents[2]
DEV_DB = "smart_lab_equipment_db"
TEST_DB = "smart_lab_equipment_apptest"
BUILD_FILES = ["01_create_database.sql", "02_create_tables.sql", "03_insert_sample_data.sql",
               "08_create_views.sql", "11_transaction_procedures.sql", "12_maintenance_procedures.sql"]
REFERENCE_DATE = "2026-10-10"


def connection_settings():
    return {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", "3306")),
        "user": os.environ.get("DB_USER", "root"),
        "password": os.environ.get("DB_PASSWORD", ""),
        "unix_socket": os.environ.get("DB_UNIX_SOCKET", ""),
    }


@pytest.fixture(scope="session")
def build_script():
    """All build files concatenated, retargeted at the test database."""
    sql = "\n".join(
        (ROOT / "sql" / name).read_text(encoding="utf-8").replace(DEV_DB, TEST_DB)
        for name in BUILD_FILES)
    return f"DROP DATABASE IF EXISTS {TEST_DB};\n{sql}"


@pytest.fixture(scope="session")
def mysql_cli_args():
    s = connection_settings()
    # The password goes into a temporary option file, not the command line.
    option_file = tempfile.NamedTemporaryFile("w", suffix=".cnf", delete=False)
    option_file.write(f"[client]\nuser={s['user']}\npassword={s['password']}\n")
    option_file.close()
    args = [os.environ.get("MYSQL_CLI", "mysql"), f"--defaults-extra-file={option_file.name}"]
    if s["unix_socket"]:
        args.append(f"--socket={s['unix_socket']}")
    else:
        args += [f"--host={s['host']}", f"--port={s['port']}"]
    yield args
    os.unlink(option_file.name)


@pytest.fixture(autouse=True)
def fresh_database(build_script, mysql_cli_args):
    result = subprocess.run(mysql_cli_args, input=build_script, text=True, capture_output=True)
    assert result.returncode == 0, f"Building the test database failed:\n{result.stderr}"
    yield


@pytest.fixture
def app():
    s = connection_settings()
    return create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "DB_HOST": s["host"], "DB_PORT": s["port"], "DB_USER": s["user"],
        "DB_PASSWORD": s["password"], "DB_UNIX_SOCKET": s["unix_socket"],
        "DB_NAME": TEST_DB,
        "REFERENCE_DATE": REFERENCE_DATE,
    })


class Client:
    """Test client that sends the CSRF token automatically on POST."""

    def __init__(self, flask_client):
        self.raw = flask_client
        with flask_client.session_transaction() as sess:
            sess["csrf_token"] = "test-token"

    def get(self, url, **kw):
        return self.raw.get(url, **kw)

    def post(self, url, data=None, **kw):
        data = dict(data or {})
        data.setdefault("csrf_token", "test-token")
        return self.raw.post(url, data=data, **kw)


@pytest.fixture
def client(app):
    return Client(app.test_client())


@pytest.fixture
def sql():
    """Run a query directly against the test database (for checking results)."""
    s = connection_settings()
    options = dict(user=s["user"], password=s["password"], database=TEST_DB)
    if s["unix_socket"]:
        options["unix_socket"] = s["unix_socket"]
    else:
        options.update(host=s["host"], port=s["port"])
    conn = mysql.connector.connect(**options)

    def run(query, params=()):
        cur = conn.cursor(dictionary=True)
        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        conn.commit()            # end the read so the next call sees new data
        return rows

    yield run
    conn.close()
