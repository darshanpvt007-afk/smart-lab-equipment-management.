"""TA01-TA06: every page loads; dashboard figures; search and filtering."""
import re

import pytest

PAGES = [
    "/", "/equipment/", "/equipment/1", "/equipment/new", "/equipment/1/edit",
    "/students/", "/students/1", "/students/new", "/students/1/edit",
    "/staff/", "/staff/new", "/staff/1/edit", "/labs/", "/labs/new", "/labs/1/edit",
    "/categories/", "/categories/new", "/categories/1/edit",
    "/suppliers/", "/suppliers/new", "/suppliers/1/edit",
    "/purchases/", "/purchases/new", "/purchases/1/edit",
    "/allocations/", "/allocations/?show=overdue", "/allocations/?show=returned",
    "/allocations/?show=all", "/allocations/new", "/allocations/17/return",
    "/maintenance/", "/maintenance/?status=Scheduled", "/maintenance/new", "/maintenance/8/complete",
    "/reports/",
]


def serials(html):
    return re.findall(r">([A-Z]{3}-[A-Z0-9]+-\d{4})<", html)


@pytest.mark.parametrize("url", PAGES)
def test_ta01_every_page_loads(client, url):
    assert client.get(url).status_code == 200


def test_ta02_unknown_records_give_404(client):
    assert client.get("/equipment/999").status_code == 404
    assert client.get("/students/999").status_code == 404
    assert client.get("/reports/no-such-report").status_code == 404


def test_ta03_dashboard_figures_match_sample_data(client):
    html = client.get("/").get_data(as_text=True)
    tiles = dict((label, int(n)) for n, label in
                 re.findall(r'<span class="n">(\d+)</span><span>([^<]+)</span>', html))
    assert tiles == {"Equipment items": 20, "Available": 11, "Issued to students": 6,
                     "Overdue": 3, "Under maintenance": 2, "Unavailable": 1}
    assert "Reference date: 2026-10-10" in html


def test_ta04_equipment_search_and_filters(client):
    get = lambda q: serials(client.get("/equipment/" + q).get_data(as_text=True))
    assert sorted(get("?q=oscilloscope")) == ["OSC-DS1-0001", "OSC-DS1-0002", "OSC-MS2-0003"]
    assert sorted(get("?q=NET-")) == ["NET-CT-0015", "NET-SW24-0012", "NET-SW24-0013", "NET-WR-0014"]
    assert len(get("?status=Available")) == 11
    assert len(get("?lab_id=4")) == 6
    assert get("?category_id=2&status=Available") == ["CLM-32-0007", "DMM-17B-0005", "DMM-17B-0006"]
    assert get("?q=does-not-exist") == []


def test_ta05_student_search_and_filters(client):
    get = lambda q: re.findall(r">(\d{2}[A-Z]{3}\d{4})</a>", client.get("/students/" + q).get_data(as_text=True))
    assert get("?q=Aarav") == ["24BCE1012"]
    assert sorted(get("?department=ECE")) == ["24BEC1045", "25BEC1077", "26BEC1062"]
    assert sorted(get("?department=CSE&year=2")) == ["25BCE1103", "25BCE1118"]
    assert len(get("")) == 10


def test_ta06_search_text_cannot_inject_sql(client, sql):
    # The search box value is sent as a query parameter, never pasted into the SQL.
    response = client.get("/equipment/?q=' OR 1=1 -- ")
    assert response.status_code == 200
    assert serials(response.get_data(as_text=True)) == []
    response = client.get("/students/?q=x'; DROP TABLE student; -- ")
    assert response.status_code == 200
    assert sql("SELECT COUNT(*) AS n FROM student")[0]["n"] == 10
