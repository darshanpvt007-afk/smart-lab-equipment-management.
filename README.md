# smart-lab-equipment-management.
Smart Laboratory Equipment Inventory, Allocation and Maintenance Management System

**Database Systems project: a MySQL database (Review 2) and a working web prototype connected to it (Review 3).**

The system records a college's laboratories, equipment, categories, suppliers, purchases, students, lab staff, equipment allocations, returns and maintenance. It implements the ER design approved in Review 1. Lab staff use a Flask web application to search the inventory, issue and receive equipment, run maintenance, keep master data up to date, and view reports.

---

## 1. What each review delivered

| Review | Requirement | Where |
|---|---|---|
| 2 | ER diagram converted into tables; primary and foreign keys; integrity constraints | `sql/02_create_tables.sql`, `docs/RELATIONAL_SCHEMA.md`, `docs/DESIGN_DECISIONS.md` |
| 2 | Sample data | `sql/03_insert_sample_data.sql` |
| 2 | SELECT, WHERE, ORDER BY, GROUP BY, HAVING, aggregates, JOIN, subqueries | `sql/04`–`07`, `docs/SQL_QUERY_CATALOG.md` |
| 2 | Views | `sql/08_create_views.sql` |
| 3 | Simple user interface | `app/templates/`, `app/static/style.css` |
| 3 | Database connectivity | `app/db.py` (mysql-connector-python) |
| 3 | CRUD operations | Labs, categories, suppliers, purchases, students, staff, equipment (`app/routes/`) |
| 3 | Search and retrieval | Equipment and student search and filters; detail pages with full history |
| 3 | Important SQL queries through the application | Reports page (`app/routes/reports.py`), dashboard, issue/return/maintenance workflows calling stored procedures |
| 3 | Input validation | `app/validators.py` and HTML form attributes; database constraints as the final guard |
| 3 | Test cases | `tests/` (database, application and browser tests: 166 in total) |
| 3 | Final database | `sql/01`–`12` (`sql/12_maintenance_procedures.sql` is new in Review 3) |
| 3 | Final report and presentation | Delivered separately (see `docs/REVIEW3_IMPLEMENTATION.md`) |

## 2. Technology

| | |
|---|---|
| Database | **MySQL 8.0.16 or newer**, needed for enforced CHECK constraints and functional indexes. Tested on 8.0.46. |
| Application | **Python 3.10+**, Flask 3.1, mysql-connector-python. Tested on Python 3.13. |
| Browser | Any modern browser. The app uses no JavaScript framework and needs no internet connection. |
| Tests | `bash` + `mysql` client (database tests); `pytest` (application tests); Playwright + Chromium (optional browser walkthrough) |

## 3. Directory structure

```
.
├── README.md
├── run.py                      start the web app:  python run.py
├── requirements.txt            Flask, mysql-connector-python, pytest
├── .env.example                copy to .env and add your MySQL login (never committed)
├── pytest.ini
├── app/                        the Flask application
│   ├── __init__.py             create_app(): config, blueprints, CSRF check, error pages
│   ├── db.py                   connection per request, parameterised queries, error messages
│   ├── validators.py           form validation that mirrors the database rules
│   ├── routes/                 dashboard, equipment, allocations, maintenance, students,
│   │                           staff, labs, categories, suppliers, purchases, reports
│   ├── templates/              Jinja HTML pages + shared form macros
│   └── static/style.css
├── sql/
│   ├── 01_create_database.sql … 03_insert_sample_data.sql
│   ├── 04_basic_queries.sql … 07_subqueries.sql        Q01–Q49
│   ├── 08_create_views.sql                              4 views + Q50–Q55
│   ├── 09_validation_queries.sql                        V01–V16
│   ├── 10_reset_database.sql                            DESTRUCTIVE: drops the database
│   ├── 11_transaction_procedures.sql                    sp_allocate_equipment, sp_return_equipment
│   └── 12_maintenance_procedures.sql                    sp_start_maintenance, sp_complete_maintenance
├── tests/
│   ├── run_tests.sh            database tests TC01–TC71
│   ├── web/                    application tests TA01–TA32 (pytest)
│   ├── browser_walkthrough.py  browser tests TB01–TB10 + screenshots
│   ├── test_cases.md           every test case described
│   └── README.md
└── docs/
    ├── REVIEW3_IMPLEMENTATION.md   Review 3: requirement mapping, app design, how to demo
    ├── FACULTY_DEMONSTRATION.md    demo scripts (SQL and app) + viva Q&A
    ├── TEST_REPORT.md              results of the latest test runs
    ├── DESIGN_DECISIONS.md         D-01 … D-22
    ├── RELATIONAL_SCHEMA.md, NORMALIZATION.md, SQL_QUERY_CATALOG.md
    ├── TROUBLESHOOTING.md
    ├── REVIEW2_IMPLEMENTATION_PLAN.md
    └── screenshots/                captured by the browser walkthrough
```

## 4. Design summary

```
supplier ──1:N── purchase ──1:N── equipment ──N:1── equipment_category
                                    │    └──N:1── lab
                    ┌───────────────┼──────────────────┐
                   1:N             1:N                1:N
      equipment_allocation ──N:1── student        maintenance ──N:1── lab_staff
             │      └──N:1── lab_staff (issued by)
            1:1 (optional)
      equipment_return
```

| Topic | How it works |
|---|---|
| Keys | Integer `AUTO_INCREMENT` primary keys. Each foreign key is `NOT NULL` and `ON DELETE RESTRICT`, so history can never be deleted by cascade. |
| Business identifiers | Register numbers, serial numbers, e-mails and invoice numbers (unique per supplier) are `UNIQUE`. |
| One active allocation | A functional UNIQUE index lets each equipment item have only one active (`Issued`) allocation. It holds even under concurrent transactions. |
| Status changes | Changes that touch several tables run in stored procedures: one transaction, row locks, rollback on any error. The app calls these procedures and never updates a status directly. |
| Application layers | browser → route (one Flask blueprint per area) → validators → `db.py` (parameterised SQL only) → MySQL. |

## 5. Set up the database

Install **MySQL Server 8.0** (<https://dev.mysql.com/downloads/mysql/>; Ubuntu `sudo apt install mysql-server`; macOS `brew install mysql`). Then, from the project folder:

```bash
mysql -u root -p < sql/01_create_database.sql
mysql -u root -p < sql/02_create_tables.sql
mysql -u root -p < sql/03_insert_sample_data.sql
mysql -u root -p < sql/08_create_views.sql
mysql -u root -p < sql/11_transaction_procedures.sql
mysql -u root -p < sql/12_maintenance_procedures.sql
```

Windows PowerShell does not support `<`. Use `Get-Content sql\01_create_database.sql | mysql -u root -p`, or `SOURCE sql/01_create_database.sql;` inside the `mysql` client.

It is better to give the application its own MySQL account than to use `root`:

```sql
CREATE USER 'labadmin'@'localhost' IDENTIFIED BY 'choose-a-password';
GRANT ALL PRIVILEGES ON smart_lab_equipment_db.* TO 'labadmin'@'localhost';
```

## 6. Run the web application

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # Windows: copy .env.example .env
# edit .env: DB_USER, DB_PASSWORD, SECRET_KEY
python run.py
```

Then open **http://127.0.0.1:5000**.

- **Configuration:** settings come from environment variables or the git-ignored `.env` file. Passwords never appear in the code.
- **Demo date:** `APP_REFERENCE_DATE=2026-10-10` makes "today" match the sample data, so the dashboard shows the 3 overdue loans. Remove that line for real use.

| Page | What it does |
|---|---|
| Dashboard | Inventory counts by status, overdue loans with a Return button, open maintenance jobs |
| Equipment | Search by name or serial; filter by lab, category and availability; add, edit, delete; detail page with allocation and maintenance history |
| Allocations | Issued / overdue / returned / all lists; Issue form (`sp_allocate_equipment`); Return form (`sp_return_equipment`) |
| Maintenance | Schedule a job; Start (`sp_start_maintenance`); Complete with cost and condition (`sp_complete_maintenance`) |
| Students | Search by name or register number; filter by department and year; add, edit, delete; history |
| Staff, Labs, Categories, Suppliers, Purchases | List with counts and totals; add, edit, delete |
| Reports | 8 reports, each showing its SQL next to the live result |

## 7. Run the SQL scripts directly (Review 2)

```bash
mysql -u root -p -t < sql/04_basic_queries.sql        # Q01–Q15
mysql -u root -p -t < sql/05_aggregate_queries.sql    # Q16–Q27
mysql -u root -p -t < sql/06_join_queries.sql         # Q28–Q38
mysql -u root -p -t < sql/07_subqueries.sql           # Q39–Q49
mysql -u root -p -t < sql/08_create_views.sql         # views + Q50–Q55
mysql -u root -p -t < sql/09_validation_queries.sql   # V01–V16
```

## 8. Run the tests

All three suites build their own separate databases and never touch `smart_lab_equipment_db`.

```bash
bash tests/run_tests.sh                     # database: expect "Passed: 71   Failed: 0   Total: 71"
python -m pytest                            # application: expect "85 passed"
python tests/browser_walkthrough.py         # optional, needs: pip install playwright && python -m playwright install chromium
```

Both the application tests and the browser walkthrough read the same `DB_*` environment variables as the app. On Windows, run `run_tests.sh` from Git Bash or WSL. More detail is in `tests/README.md`; results are in `docs/TEST_REPORT.md`.

## 9. Reset the development database (destructive)

`sql/10_reset_database.sql` runs `DROP DATABASE smart_lab_equipment_db`, permanently deleting everything in it. Nothing runs it automatically. Back up first, then rebuild with section 5:

```bash
mysqldump -u root -p --routines smart_lab_equipment_db > backup.sql
mysql -u root -p < sql/10_reset_database.sql
```

## 10. Common errors

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'flask'` | Activate the virtual environment, then `pip install -r requirements.txt` |
| App shows "Error 500 … Check that the MySQL server is running" | Start MySQL; check `DB_USER` / `DB_PASSWORD` in `.env` |
| `Access denied for user` | Wrong credentials in `.env`, or the account lacks privileges (section 5) |
| `Address already in use` on port 5000 | Set `PORT=5001` in `.env` |
| "The form has expired" | The session restarted; reload the page and submit again |
| `PROCEDURE … does not exist` | Run `sql/11_…` and `sql/12_…` |

More in `docs/TROUBLESHOOTING.md`.

## 11. Known limitations

- No login or user roles.
- Reminders are shown on the dashboard, not e-mailed.
- Department is free text.
- No retired status for equipment.
- Tested on Linux with MySQL 8.0.46 only.

`docs/REVIEW3_IMPLEMENTATION.md` lists the suggested next steps.
