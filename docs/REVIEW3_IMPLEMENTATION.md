# Review 3 Implementation: Working Prototype

**Deadline:** 26 October 2026. **Expected outcome (course instructions):** "A working prototype connected to the database."

Review 3 adds a Python Flask web application on top of the unchanged Review 2 database, plus two stored procedures for the maintenance workflow. Everything was run and tested on MySQL 8.0.46 with Python 3.13 (see `TEST_REPORT.md`).

## 1. Requirement → implementation → evidence

| Review 3 requirement | Implementation | Tests |
|---|---|---|
| Simple user interface | 11 page groups behind one navigation bar (`app/templates/`), one stylesheet, no JavaScript framework | TA01, TB01–TB10 |
| Database connectivity | `app/db.py`: mysql-connector-python, one connection per request, `autocommit` off, commit or rollback per write | every TA test |
| CRUD operations | Create / list / edit / delete for labs, categories, suppliers, purchases, students, staff, equipment | TA07–TA19 |
| Search / retrieval | Equipment: text (name or serial) + lab + category + availability. Students: text (name or register number) + department + year. Detail pages for equipment and students with full history | TA04–TA06, TB02, TB03, TB10 |
| Important SQL queries through the application | Reports page runs 8 Review 2 queries and prints their SQL. Dashboard and lists use the views. Workflows call the 4 stored procedures | TA20–TA29, TB05, TB06, TB08, TB09 |
| Input validation | `app/validators.py` (required, length, format, range, money, date rules) + HTML attributes; database constraints remain the final guard; database errors become plain messages | TA08, TA09, TA13, TA17, TA19, TA22, TA24, TA25, TA32, TB04, TB07 |
| Test cases | 71 database + 85 application + 10 browser tests | `TEST_REPORT.md` |
| Final database | `sql/01`–`12` | TC01–TC71 |
| Final project report, presentation | Delivered separately as a shareable document and a slide deck (exportable to Word/PDF and PowerPoint/PDF) | — |

## 2. Application structure

| File | Responsibility |
|---|---|
| `run.py` | Loads `.env` (if present), creates the app, serves it on 127.0.0.1:5000 |
| `app/__init__.py` | `create_app()`: configuration from environment variables, blueprint registration, CSRF check on every POST, error pages, the `today()` reference date |
| `app/db.py` | `query_all`, `query_one`, `execute`, `call_procedure`; `friendly_error()` maps MySQL errors 1048/1062/1451/1452/3819/1644 to messages |
| `app/validators.py` | `Form` helper: `text`, `email`, `phone`, `integer`, `money`, `date`, `choice` |
| `app/routes/*.py` | One blueprint per area; each SQL statement is written in full in the route that uses it |
| `app/templates/` | `base.html` (navigation, flash messages), `macros.html` (form fields, delete button, status badge), one folder per area |

## 3. Decisions made in Review 3

These decisions are recorded in `DESIGN_DECISIONS.md` as D-20 to D-22.

- **Statuses change only through workflows.** Equipment condition and availability, allocation status and maintenance status can never be edited in a plain form. They change only by issue, return, start or complete, each a stored procedure. This keeps the stored status consistent with the history, which test TA27 checks.
- **The database is the final guard.** The app validates first for friendly messages, but every rule is still enforced by MySQL. The friendly-error mapping keeps those errors readable.
- **The demo date is fixed.** `APP_REFERENCE_DATE` fixes "today" for the demonstration; without it the real date is used.
- **No login.** The course requirements do not ask for one; it is listed as the first future enhancement.

## 4. Demonstrating the prototype

`FACULTY_DEMONSTRATION.md` part B has the step-by-step script with expected results. In short:

1. Rebuild the database (README section 5) so the sample data is in its documented state.
2. Set `APP_REFERENCE_DATE=2026-10-10` in `.env`, then run `python run.py`.
3. Follow the 7 demo steps: dashboard → search → add student (and a duplicate) → issue (and an invalid date) → return → maintenance start/complete → a report.

## 5. Known limitations and next steps

| Limitation | Next step |
|---|---|
| No login; anyone who can open the app can change data | User accounts with roles and an audit column |
| Overdue loans and due maintenance are shown, not sent | Scheduled e-mail reminders using the existing queries |
| Department is free text | A department lookup table (needs ER approval) |
| Items can only be kept or deleted | A Retired status that keeps the history |
| Tested on Linux only | Run the suites on the lab's Windows machines |
