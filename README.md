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
| 3 | Test cases | `tests/` (database, application and browser tests: 252 in total) |
| 3 | Final database | `sql/01`–`12` (`sql/12_maintenance_procedures.sql` is new in Review 3) |
| 3 | Final report and presentation | Delivered separately (see `docs/REVIEW3_IMPLEMENTATION.md`) |
| Deployment | Sign-in, roles, web security, least-privilege database accounts, production server, backups | `docs/SECURITY.md`, `docs/DEPLOYMENT.md`, `app/auth.py`, `sql/13_app_users.sql` |

## 2. Technology

| | |
|---|---|
| Database | **MySQL 8.0.16 or newer**, needed for enforced CHECK constraints and functional indexes. Tested on 8.0.46. |
| Application | **Python 3.10+**, Flask 3.1, mysql-connector-python; gunicorn for production. Tested on Python 3.13. |
| Browser | Any modern browser. The app uses no JavaScript framework and needs no internet connection. |
| Tests | `bash` + `mysql` client (database tests); `pytest` (application tests); Playwright + Chromium (optional browser walkthrough) |

## 3. Directory structure

```
.
├── README.md
├── run.py                      start the web app locally:  python run.py
├── wsgi.py, gunicorn.conf.py   production entry point:  gunicorn --config gunicorn.conf.py wsgi:app
├── requirements.txt            Flask, mysql-connector-python, gunicorn, pytest
├── .env.example                copy to .env and add your MySQL login (placeholders only; .env is never committed)
├── pytest.ini
├── app/                        the Flask application
│   ├── __init__.py             create_app(): config checks, blueprints, CSRF, security headers, error pages
│   ├── auth.py                 sign-in, roles, permission for every route, login throttling
│   ├── db.py                   connection per request, parameterised queries, error messages
│   ├── validators.py           form validation that mirrors the database rules
│   ├── routes/                 dashboard, equipment, allocations, maintenance, students,
│   │                           staff, labs, categories, suppliers, purchases, reports,
│   │                           auth (sign-in), users, health (/healthz),
│   │                           portal (students: /my/), requests (staff approval)
│   ├── templates/              Jinja HTML pages + shared form macros
│   └── static/style.css
├── sql/
│   ├── 01_create_database.sql … 03_insert_sample_data.sql
│   ├── 04_basic_queries.sql … 07_subqueries.sql        Q01–Q49
│   ├── 08_create_views.sql                              4 views + Q50–Q55
│   ├── 09_validation_queries.sql                        V01–V16
│   ├── 10_reset_database.sql                            DESTRUCTIVE: drops the database
│   ├── 11_transaction_procedures.sql                    sp_allocate_equipment, sp_return_equipment
│   ├── 12_maintenance_procedures.sql                    sp_start_maintenance, sp_complete_maintenance
│   ├── 13_app_users.sql                                 sign-in tables (additive, safe to re-run)
│   ├── 15_student_portal.sql                            student accounts + borrowing requests (additive)
│   └── 14_db_accounts.sql.example                       template for the three MySQL accounts
├── tests/
│   ├── run_tests.sh            database tests TC01–TC83
│   ├── web/                    application tests TA01–TA92 (pytest)
│   ├── browser_walkthrough.py  browser tests TB00–TB18 + screenshots
│   ├── test_cases.md           every test case described
│   └── README.md
└── docs/
    ├── REVIEW3_IMPLEMENTATION.md   Review 3: requirement mapping, app design, how to demo
    ├── SECURITY.md                 roles and permissions, security controls, limitations
    ├── DEPLOYMENT.md               hosting options, accounts, environment, backups and restore
    ├── FACULTY_DEMONSTRATION.md    demo scripts (SQL and app) + viva Q&A
    ├── TEST_REPORT.md              results of the latest test runs
    ├── DESIGN_DECISIONS.md         D-01 … D-25
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

Install **MySQL Server 8.0.16 or newer** (<https://dev.mysql.com/downloads/mysql/>; macOS `brew install mysql`).

**Ubuntu.** The `mysql-server` package sets up `root` with socket authentication: root has no password and signs in through `sudo`. So on Ubuntu, `mysql -u root -p` fails with *Access denied for user 'root'@'localhost'*; use `sudo mysql` instead.

```bash
sudo apt update
sudo apt install mysql-server
sudo systemctl start mysql              # if it is not already running
sudo mysql -e "SELECT VERSION();"       # must be 8.0.16 or newer
```

Then, from the project folder, build the database:

```bash
# Ubuntu (root via sudo)
for f in 01_create_database 02_create_tables 03_insert_sample_data \
         08_create_views 11_transaction_procedures 12_maintenance_procedures 13_app_users \
         15_student_portal; do
  sudo mysql < sql/$f.sql
done

# Other systems where root has a password: the same loop with
#   mysql -u root -p < sql/$f.sql
```

Windows PowerShell does not support `<`. Use `Get-Content sql\01_create_database.sql | mysql -u root -p`, or `SOURCE sql/01_create_database.sql;` inside the `mysql` client.

Give the application its own MySQL account instead of `root` (choose your own password). The last two grants are only needed to run the tests (section 8), which build these two separate test databases:

```bash
sudo mysql <<'SQL'
CREATE USER 'labadmin'@'localhost' IDENTIFIED BY 'choose-a-password';
GRANT ALL PRIVILEGES ON smart_lab_equipment_db.*      TO 'labadmin'@'localhost';
GRANT ALL PRIVILEGES ON smart_lab_equipment_test.*    TO 'labadmin'@'localhost';
GRANT ALL PRIVILEGES ON smart_lab_equipment_apptest.* TO 'labadmin'@'localhost';
SQL
```

If MySQL answers *Your password does not satisfy the current policy requirements*, the `validate_password` component is on: choose a longer password with upper case, lower case, a digit and a symbol.

**Upgrading a database built before the register-number check.** Script 02 now includes `chk_student_register_no` (format `24BCE1012`). A database built earlier keeps working without it. To add it without rebuilding (it fails, and changes nothing, if any stored register number does not match):

```bash
sudo mysql smart_lab_equipment_db -e "ALTER TABLE student ADD CONSTRAINT chk_student_register_no CHECK (REGEXP_LIKE(register_number, '^[0-9]{2}[A-Z]{3}[0-9]{4}\$', 'c'));"
```

## 6. Run the web application

```bash
sudo apt install python3 python3-venv python3-pip   # Ubuntu, once
python3 -m venv .venv                # Windows: python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # Windows: copy .env.example .env
nano .env                            # set DB_USER=labadmin, DB_PASSWORD, SECRET_KEY
flask --app run create-user --username your.name --role admin   # first account; asks for a password (12+ characters)
python run.py
```

Generate a `SECRET_KEY` with `python -c "import secrets; print(secrets.token_hex(32))"`. Inside the activated virtual environment, `python` means the environment's Python 3.

Then open **http://127.0.0.1:5000** and sign in with the account you just created. There are no default accounts. Administrators add more accounts on the **Users** page; each person gets one of four roles (admin, lab manager, inventory staff, technician). `docs/SECURITY.md` lists what each role may do.

Already have a database from before sign-in was added? Run only the migrations you are missing: `sudo mysql < sql/13_app_users.sql` (staff sign-in) and `sudo mysql < sql/15_student_portal.sql` (student accounts and requests). They only add tables and never change existing data.

**Students.**
1. An administrator opens **Users → Student sign-in** and clicks **Open activation for all students without an account**.
2. Each student goes to the sign-in page, clicks **Activate your account**, and enters their register number, the e-mail on record and a password they choose.
3. Students then sign in with their register number. They see only their own loans and requests, and can request available equipment.
4. Staff approve or reject requests on **Student requests**.

For an HTTPS deployment (production server, least-privilege database accounts, backups, hosting options) see `docs/DEPLOYMENT.md`.

- **Configuration:** settings come from environment variables or the git-ignored `.env` file. Passwords never appear in the code.
- **Demo date:** `APP_REFERENCE_DATE=2026-10-10` makes "today" match the sample data, so the dashboard shows the 3 overdue loans. Remove that line for real use.

| Page | What it does |
|---|---|
| Sign in | Username and password; repeated failures are slowed down; sign out from the account menu (top right) |
| Users (admin) | Create accounts, choose roles, deactivate, reset passwords; Student sign-in: open, reset or deactivate student accounts |
| Student requests | Staff approve (issues the item via `sp_allocate_equipment`) or reject students' borrowing requests |
| My equipment (students) | A student's own loans, requests and history, and the list of available equipment with a Request button |
| Layout | Top bar with global search (press `/`) and the reference date; sidebar grouped into Inventory, Loans, People, Procurement and Administration with live counts; breadcrumbs; menu button on phones |
| Dashboard | Operations overview: cards for available items, items on loan, overdue loans and maintenance (with cost committed and spent); overdue loans with who issued them and a *Record return* button; items due in the next 4 days; loans issued per month; lab utilisation; recent activity |
| Equipment | Saved views (All, Available, On loan, Needs attention) with counts; search by name or serial; filter by lab, category and availability; sortable columns; last activity; one action per row (Issue, Record return, Start job, Complete job, Schedule repair); 10/25/50 rows per page; Export CSV; add, edit, delete |
| Equipment page | Status and overdue banner, key facts and lifetime maintenance cost, lifecycle timeline, Loans and Maintenance tabs |
| Allocations | Issued / overdue / returned / all lists; Issue form (`sp_allocate_equipment`) with quick due dates, live pre-issue checks and Ctrl+Enter; Return form (`sp_return_equipment`) |
| Maintenance | Schedule a job; Start (`sp_start_maintenance`); Complete with cost and condition (`sp_complete_maintenance`) |
| Students | Search by name or register number; filter by department and year; add, edit, delete; history |
| Staff, Labs, Categories, Suppliers, Purchases | List with counts and totals; add, edit, delete |
| Reports | 8 reports, each showing its SQL next to the live result |
| Search | One search across equipment, students, staff and labs |

## 7. Run the SQL scripts directly (Review 2)

```bash
sudo mysql -t < sql/04_basic_queries.sql        # Q01–Q15   (other systems: mysql -u root -p -t < …)
sudo mysql -t < sql/05_aggregate_queries.sql    # Q16–Q27
sudo mysql -t < sql/06_join_queries.sql         # Q28–Q38
sudo mysql -t < sql/07_subqueries.sql           # Q39–Q49
sudo mysql -t < sql/08_create_views.sql         # views + Q50–Q55
sudo mysql -t < sql/09_validation_queries.sql   # V01–V16
```

## 8. Run the tests

All three suites build their own separate databases (`smart_lab_equipment_test` and `smart_lab_equipment_apptest`), drop and rebuild them freely, and never touch `smart_lab_equipment_db`.

```bash
# database tests (Ubuntu: run the mysql client through sudo)
MYSQL_CMD="sudo mysql" bash tests/run_tests.sh   # expect "Passed: 83   Failed: 0   Total: 83"

# application tests, as labadmin (needs the test-database grants from section 5)
export DB_USER=labadmin
read -rsp "MySQL password for labadmin: " DB_PASSWORD; echo; export DB_PASSWORD
python -m pytest                                 # expect "150 passed"

# optional browser walkthrough: needs  pip install playwright && python -m playwright install chromium
# NOTE: it rewrites the screenshots in docs/screenshots/
python tests/browser_walkthrough.py              # expect "Passed: 19   Failed: 0   Total: 19"
```

The application tests and the browser walkthrough read the same `DB_*` environment variables as the app; `read -s` keeps the password off the screen and out of the shell history. On systems where root has a password, run the database tests with `MYSQL_CMD="mysql -u root -p"`. On Windows, run `run_tests.sh` from Git Bash or WSL. More detail is in `tests/README.md`; results are in `docs/TEST_REPORT.md`.

## 9. Reset the development database (destructive)

`sql/10_reset_database.sql` runs `DROP DATABASE smart_lab_equipment_db`, permanently deleting everything in it. Nothing runs it automatically. Back up first, then rebuild with section 5:

```bash
sudo mysqldump --routines smart_lab_equipment_db > backup.sql   # other systems: mysqldump -u root -p …
sudo mysql < sql/10_reset_database.sql                          # other systems: mysql -u root -p < …
```

## 10. Common errors

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'flask'` | Activate the virtual environment, then `pip install -r requirements.txt` |
| App shows "Error 500 … An unexpected error occurred" | Start MySQL; check `DB_USER` / `DB_PASSWORD` in `.env`; the terminal running the app shows the details |
| `Table '…app_user' doesn't exist` | Run `sudo mysql < sql/13_app_users.sql` |
| `Table '…student_account' doesn't exist` (or `equipment_request`) | Run `sudo mysql < sql/15_student_portal.sql` |
| Student: "These details do not match a student account…" | Activation is not open for them, has expired, or the e-mail differs from the one on record: an admin clicks **Reset** / **Open activation** on Student sign-in |
| "Too many failed sign-in attempts" | Wait 15 minutes, or ask an administrator to reset the password |
| `Refusing to start in production: …` | A required setting is missing or unsafe; the message names it (docs/DEPLOYMENT.md section 5) |
| `Access denied for user 'root'@'localhost'` on Ubuntu | Root uses socket authentication: run `sudo mysql` instead of `mysql -u root -p` (section 5) |
| `Access denied for user 'labadmin'…` | Wrong credentials in `.env`, or the account lacks privileges (section 5) |
| `Error: Command '[…]/python3', '-m', 'ensurepip'…` when creating `.venv` | `sudo apt install python3-venv` |
| `Address already in use` on port 5000 | Set `PORT=5001` in `.env` |
| "The form has expired" | The session restarted; reload the page and submit again |
| `PROCEDURE … does not exist` | Run `sql/11_…` and `sql/12_…` |

More in `docs/TROUBLESHOOTING.md`.

## 11. Known limitations

- No multi-factor authentication or self-service password reset (an administrator resets passwords).
- Reminders are shown on the dashboard, not e-mailed.
- Department is free text.
- No retired status for equipment.
- Tested on Linux with MySQL 8.0.46 only.

`docs/REVIEW3_IMPLEMENTATION.md` lists the suggested next steps.
