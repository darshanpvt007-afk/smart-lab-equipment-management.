"""TA01-TA06: every page loads; dashboard figures; search and filtering.
TA40-TA47: enterprise UI features (saved views, sorting, paging, CSV export,
global search, equipment detail tabs and lifecycle, sidebar counts)."""
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
    "/reports/", "/search", "/search?q=meter", "/equipment/1?tab=loans", "/equipment/1?tab=maintenance",
    "/equipment/?view=attention&sort=activity&dir=desc&per_page=10&page=2",
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
    kpis = dict((label, int(n)) for label, n in re.findall(
        r'<p class="kpi-label">([^<]+)</p>\s*<p class="kpi-value"><span class="kpi-n">(\d+)</span>', html))
    assert kpis == {"Available now": 11, "On loan": 6, "Overdue": 3, "Maintenance": 2}
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
    for fact in ("11 of 20", "55% of the inventory can be issued", "3 issued in the last 7 days",
                 "Oldest 12 days late · 50% of loans", "2 in progress · 2 scheduled",
                 "₹9,700 committed · ₹10,450 spent to date",
                 "Due in the next 4 days: Kabir Nair (12 Oct), Ishaan Rao (13 Oct), Diya Raghavan (14 Oct)",
                 "August was the busiest month, with 7 loans."):
        assert fact in text, fact
    # Overdue table: most overdue first, with who issued the item.
    assert re.findall(r"(Vikram Joshi|Rohan Kulkarni|Aarav Menon).*?(\d+) d</span>", html, re.S) == \
        [("Vikram Joshi", "12"), ("Rohan Kulkarni", "5"), ("Aarav Menon", "2")]
    # Loans per month Jul-Oct, and lab utilisation (share on loan) busiest lab first.
    assert re.findall(r'<span class="bar-n">(\d+)</span>', html) == ["4", "7", "5", "4"]
    assert re.findall(r'lab_id=\d+">([^<]+)</a>.*?<td class="num">(\d+)%</td>', html, re.S) == [
        ("Embedded Systems Lab", "33"), ("Computer Networks Lab", "50"),
        ("Electronics and Circuits Lab", "40"), ("Applied Physics Lab", "0")]
    assert "Ramesh Kumar</b> issued Wireless Router to <b>Diya Raghavan" in html     # newest event first
    assert "Reference date: 2026-10-10" in html


def test_ta47_sidebar_counts(client):
    html = client.get("/students/").get_data(as_text=True)
    counts = re.findall(r'<span class="nav-count[^"]*">([^<]+)</span>', html)
    assert counts == ["20", "4 open", "3 overdue", "10", "4", "1 open"]


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


def test_ta40_saved_views_and_counts(client):
    page = lambda q: client.get("/equipment/" + q).get_data(as_text=True)
    html = page("")
    assert re.findall(r'<span class="tab-count">(\d+)</span>', html) == ["20", "11", "6", "3"]
    assert sorted(serials(page("?view=attention"))) == ["MCU-ARD-0009", "OSC-MS2-0003", "PSU-DC30-0017"]
    assert len(serials(page("?view=on_loan"))) == 6
    # Tab counts follow the other filters: lab 4 (Embedded Systems) has 6 items.
    assert re.findall(r'<span class="tab-count">(\d+)</span>', page("?lab_id=4")) == ["6", "2", "2", "2"]
    assert len(serials(page("?view=bogus"))) == 20                  # unknown view -> all


def test_ta41_sorting_is_whitelisted(client, sql):
    get = lambda q: serials(client.get("/equipment/" + q).get_data(as_text=True))
    assert get("?sort=activity&dir=desc")[:3] == ["NET-WR-0014", "PSU-DC30-0017", "MCU-RPI-0010"]
    by_lab = get("?sort=lab")
    labs = [r["serial_number"] for r in sql(
        "SELECT e.serial_number FROM equipment e JOIN lab l ON l.lab_id = e.lab_id "
        "ORDER BY l.lab_name, e.equipment_name, e.serial_number")]
    assert by_lab == labs
    # An unknown sort key (or SQL in it) falls back to the default order.
    response = client.get("/equipment/?sort=equipment_id;DROP TABLE lab&dir=sideways")
    assert response.status_code == 200
    assert serials(response.get_data(as_text=True)) == get("")
    assert sql("SELECT COUNT(*) AS n FROM lab")[0]["n"] == 4


def test_ta42_pagination(client):
    get = lambda q: client.get("/equipment/" + q).get_data(as_text=True)
    first, second = get("?per_page=10"), get("?per_page=10&page=2")
    assert len(serials(first)) == 10 and len(serials(second)) == 10
    assert not set(serials(first)) & set(serials(second))
    assert "1–10 of 20" in first and "11–20 of 20" in second
    assert serials(get("?per_page=10&page=99")) == serials(second)  # past the end -> last page
    assert len(serials(get("?per_page=7"))) == 20                   # only 10/25/50 allowed


def test_ta43_csv_export_follows_filters(client):
    response = client.get("/equipment/export.csv?view=on_loan&sort=lab")
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert "attachment; filename=equipment-2026-10-10.csv" == response.headers["Content-Disposition"]
    lines = response.get_data(as_text=True).splitlines()
    assert lines[0].startswith("Serial number,Equipment,Category,Laboratory")
    assert len(lines) == 1 + 6
    assert any(line.startswith("OSC-DS1-0001,") and "Aarav Menon,2026-10-08" in line for line in lines)


def test_ta44_csv_export_neutralises_formulas(client, sql):
    data = {"equipment_name": "=HYPERLINK(\"http://x\")", "serial_number": "CSV-01-0001",
            "category_id": "1", "lab_id": "1", "purchase_id": "1", "equipment_condition": "New"}
    assert client.post("/equipment/new", data).status_code == 302
    csv_text = client.get("/equipment/export.csv?q=CSV-01").get_data(as_text=True)
    assert "'=HYPERLINK" in csv_text


def test_ta45_global_search(client):
    html = client.get("/search?q=menon").get_data(as_text=True)
    assert "Aarav Menon" in html and "1 result for" in html
    html = client.get("/search?q=OSC-DS1").get_data(as_text=True)
    assert serials(html) == ["OSC-DS1-0001", "OSC-DS1-0002"]
    assert html.count('href="/equipment/1"') == 1 and html.count('href="/equipment/2"') == 1
    assert "2 results for" in html
    assert "0 results for" in client.get("/search?q=' OR 1=1 -- ").get_data(as_text=True)


def test_ta46_equipment_detail_tabs_and_lifecycle(client):
    html = client.get("/equipment/1").get_data(as_text=True)
    assert "Overdue 2 days" in html
    assert "On loan to" in html and "Aarav Menon" in html
    steps = re.findall(r'<li class="tl-([a-z-]+)">', html)
    assert steps == ["issued", "maint-completed", "returned", "issued", "maint-completed", "received"]
    assert "2 loans · 2 maintenance jobs · ₹4,250 spent" in re.sub(r"\s+", " ", html)
    loans = client.get("/equipment/1?tab=loans").get_data(as_text=True)
    assert "Faulty power switch" not in loans and loans.count("<tr>") == 1 + 2
    jobs = client.get("/equipment/1?tab=maintenance").get_data(as_text=True)
    assert "Total spent on completed jobs" in jobs and "4,250.00" in jobs
