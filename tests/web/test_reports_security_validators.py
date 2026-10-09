"""TA28-TA32: reports run the important SQL queries; CSRF and HTML
escaping; unit tests of the validation helpers (no database needed)."""
import re
from datetime import date
from decimal import Decimal

import pytest

from app.routes.reports import REPORTS
from app.validators import Form


def rows_in(html):
    body = html.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
    return [re.findall(r"<td>(.*?)</td>", tr) for tr in re.findall(r"<tr>(.*?)</tr>", body, re.S)]


@pytest.mark.parametrize("report", REPORTS, ids=[r["slug"] for r in REPORTS])
def test_ta28_every_report_runs_and_shows_its_sql(client, report):
    response = client.get(f"/reports/{report['slug']}")
    assert response.status_code == 200
    assert "SELECT" in response.get_data(as_text=True)


def test_ta29_report_results_match_review2_answers(client):
    overdue = rows_in(client.get("/reports/overdue").get_data(as_text=True))
    assert [(r[0], r[-1]) for r in overdue] == [("15", "12"), ("16", "5"), ("17", "2")]
    spend = rows_in(client.get("/reports/supplier-spend").get_data(as_text=True))
    assert [r[2] for r in spend] == ["208500.00", "72500.00", "68700.00", "39000.00"]
    never = rows_in(client.get("/reports/never-maintained").get_data(as_text=True))
    assert len(never) == 10
    borrowers = rows_in(client.get("/reports/frequent-borrowers").get_data(as_text=True))
    assert [r[0] for r in borrowers] == ["24BCE1012", "24BEC1045", "25BCE1118", "23BCE1009"]


def test_ta30_post_without_csrf_token_is_rejected(app, sql):
    raw = app.test_client()
    response = raw.post("/labs/new", data={"lab_name": "X", "location": "Y", "capacity": "5", "lab_type": "Z"})
    assert response.status_code == 400
    assert sql("SELECT COUNT(*) AS n FROM lab")[0]["n"] == 4


def test_ta31_user_text_is_html_escaped(client):
    client.post("/categories/new", {"category_name": "<script>alert(1)</script>"})
    html = client.get("/categories/").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


class TestTA32Validators:
    def test_text_required_length_and_upper(self):
        form = Form({"a": "  ", "b": "x" * 11, "c": "24bce1012"})
        assert form.text("a", "A") is None and form.errors["a"] == "A is required."
        form.text("b", "B", max_len=10)
        assert form.errors["b"] == "B must be at most 10 characters."
        assert form.text("c", "C", upper=True) == "24BCE1012"

    def test_integer(self):
        form = Form({"y": "abc", "z": "7"})
        assert form.integer("y", "Y") is None and "whole number" in form.errors["y"]
        assert form.integer("z", "Z", max_value=5) == 7 and form.errors["z"] == "Z must be at most 5."

    @pytest.mark.parametrize("raw,error", [
        ("12.345", "at most 2 decimal places"), ("abc", "must be a number"),
        ("NaN", "must be a number"), ("-1", "cannot be negative"),
    ])
    def test_money_rejects(self, raw, error):
        form = Form({"m": raw})
        form.money("m", "Cost")
        assert error in form.errors["m"]

    def test_money_accepts(self):
        form = Form({"m": "1250.5"})
        assert form.money("m", "Cost") == Decimal("1250.5") and form.ok

    def test_date(self):
        form = Form({"d": "2026-02-30", "e": "2026-10-11"})
        form.date("d", "D")
        assert "valid date" in form.errors["d"]
        form.date("e", "E", not_after=date(2026, 10, 10))
        assert form.errors["e"] == "E cannot be after 2026-10-10."

    @pytest.mark.parametrize("phone,ok", [("9000000101", True), ("+919000000101", True),
                                          ("12345", False), ("90000-00101", False)])
    def test_phone(self, phone, ok):
        form = Form({"p": phone})
        form.phone("p")
        assert form.ok is ok

    def test_choice(self):
        form = Form({"c": "Lost"})
        assert form.choice("c", "Status", ("Issued", "Returned")) is None
        assert form.errors["c"] == "Status must be one of: Issued, Returned."
