# Review 3 Implementation: Working Prototype

**Deadline:** 26 October 2026. **Expected outcome (course instructions):** "A working prototype connected to the database."

Review 3 adds a Python Flask web application on top of the unchanged Review 2 database, plus two stored procedures for the maintenance workflow. Everything was run and tested on MySQL 8.0.46 with Python 3.13 (see `TEST_REPORT.md`).

## 1. Requirement → implementation → evidence

| Review 3 requirement | Implementation | Tests |
|---|---|---|
| Simple user interface | Enterprise-style shell: top bar with global search, grouped sidebar with live counts, breadcrumbs; operations dashboard; equipment list with saved views, sorting, paging and CSV export; equipment page with lifecycle; guided issue form (section 6). One stylesheet, one small script, no framework | TA01, TA03, TA40–TA47, TB01–TB13 |
| Database connectivity | `app/db.py`: mysql-connector-python, one connection per request, `autocommit` off, commit or rollback per write | every TA test |
| CRUD operations | Create / list / edit / delete for labs, categories, suppliers, purchases, students, staff, equipment | TA07–TA19 |
| Search / retrieval | Equipment: text (name or serial) + lab + category + availability. Students: text (name or register number) + department + year. Global search across equipment, students, staff and labs. Detail pages for equipment and students with full history | TA04–TA06, TA45, TA46, TB02, TB03, TB10 |
| Important SQL queries through the application | Reports page runs 8 Review 2 queries and prints their SQL. Dashboard and lists use the views. Workflows call the 4 stored procedures | TA20–TA29, TB05, TB06, TB08, TB09 |
| Input validation | `app/validators.py` (required, length, format, range, money, date rules) + HTML attributes; database constraints remain the final guard; database errors become plain messages | TA08, TA09, TA13, TA17, TA19, TA22, TA24, TA25, TA32, TB04, TB07 |
| Test cases | 71 database + 98 application + 13 browser tests | `TEST_REPORT.md` |
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
| `app/activity.py` | One equipment timeline (purchase, loans, returns, maintenance) built with `UNION ALL` from existing tables; used by the dashboard feed, the "Last activity" column (via `ROW_NUMBER()`) and the lifecycle |
| `app/static/app.js` | Optional enhancements only: mobile menu, `/` to search, rows-per-page, Ctrl+Enter, issue-form quick dates and checks |
| `app/templates/` | `base.html` (top bar, sidebar, breadcrumbs, flash messages), `macros.html` (form fields, delete button, status badge), one folder per area |

## 3. Decisions made in Review 3

These decisions are recorded in `DESIGN_DECISIONS.md` as D-20 to D-23.

- **Statuses change only through workflows.** Equipment condition and availability, allocation status and maintenance status can never be edited in a plain form. They change only by issue, return, start or complete, each a stored procedure. This keeps the stored status consistent with the history, which test TA27 checks.
- **The database is the final guard.** The app validates first for friendly messages, but every rule is still enforced by MySQL. The friendly-error mapping keeps those errors readable.
- **The demo date is fixed.** `APP_REFERENCE_DATE` fixes "today" for the demonstration; without it the real date is used.
- **No login.** The course requirements do not ask for one; it is listed as the first future enhancement.

## 4. Demonstrating the prototype

`FACULTY_DEMONSTRATION.md` part B has the step-by-step script with expected results. In short:

1. Rebuild the database (README section 5) so the sample data is in its documented state.
2. Set `APP_REFERENCE_DATE=2026-10-10` in `.env`, then run `python run.py`.
3. Follow the 12 demo steps: dashboard → search → equipment lifecycle → add student (and a duplicate) → issue (and an invalid date) → return → maintenance start/complete → a report → a refused delete.

## 5. Known limitations and next steps

| Limitation | Next step |
|---|---|
| No login; anyone who can open the app can change data | User accounts with roles and an audit column |
| Overdue loans and due maintenance are shown, not sent | Scheduled e-mail reminders using the existing queries |
| Department is free text | A department lookup table (needs ER approval) |
| Items can only be kept or deleted | A Retired status that keeps the history |
| Tested on Linux only | Run the suites on the lab's Windows machines |
| Designed but not built: sign-in with roles, notification bell, bulk actions on the equipment list | Build on the same pages once login exists (bulk actions need a role check) |

## 6. Enterprise user interface

Designed as a mockup first (dashboard, equipment list, equipment page, issue form), then built with server-rendered templates and plain CSS. Screenshots are in `docs/screenshots/`.

| Screen | What it adds | Tests |
|---|---|---|
| App shell (`base.html`) | 56 px top bar with global search (`/` focuses it) and the reference date; grouped sidebar (Inventory, Loans, People, Procurement, Administration) with live counts; breadcrumbs; collapses to a menu button on phones | TA47, TB13 |
| Dashboard (`/`) | Four KPI cards with context; overdue loans with who issued them and a *Record return* button; loans issued per month; lab utilisation; recent activity | TA03, TB01 |
| Equipment list | Saved views with counts (All, Available, On loan, Needs attention); search and filters; sortable columns; Last activity; one contextual action per row (Issue, Record return, Start job, Complete job, Schedule repair); 10/25/50 rows per page; Export CSV of the current list | TA04, TA40–TA44, TB02, TB11 |
| Equipment page | Status and overdue banner; key facts and lifetime cost; lifecycle timeline; Loans and Maintenance tabs | TA46, TB03 |
| Issue form | Sections; available items only; quick due dates (3 days, 1 week, 2 weeks); live pre-issue checks and summary; sticky action bar; Ctrl+Enter | TA20–TA22, TB04, TB05, TB12 |
| Global search (`/search`) | Equipment, students, staff and labs in one place | TA45 |

| Screenshot | Shows |
|---|---|
| `01_dashboard.png` | Operations overview |
| `02_equipment_search.png`, `12_equipment_views.png` | Equipment list: search, saved view, sorting |
| `03_equipment_detail.png` | Equipment page with lifecycle |
| `04_issue_validation.png`, `13_issue_form.png` | Issue form: field error; quick date and checks |
| `05`–`11` | Issue, return, duplicate, maintenance, report, student pages |
| `14_mobile_menu.png` | Phone width with the menu open |
