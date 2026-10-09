# Test Cases

These are the test definitions, 252 in all, and every case is automated under the same ID. Results of the latest run are in `docs/TEST_REPORT.md`.

| IDs | Suite | Run with |
|---|---|---|
| TC01–TC83 | Database tests (A–H Review 2; I Review 3; L register-number check; N sign-in migration; P student portal) | `bash tests/run_tests.sh` |
| TA01–TA32, TA40–TA48, TA50–TA74, TA80–TA92 (150 test functions with parameters) | Web application tests (J) | `python -m pytest` |
| TB00–TB18 | Browser walkthrough (K) | `python tests/browser_walkthrough.py` |

The automated runner works on a separate database, `smart_lab_equipment_test`, rebuilt from the scripts. To try a case by hand, run its SQL in the `mysql` client against `smart_lab_equipment_db`:
- Cases marked **(rolls back)** or **(rejected)** leave the data unchanged.
- Cases marked **(changes data)** modify the database, so run `10_reset_database.sql` and rebuild afterwards if you need the original sample state.

Error codes used below:

| Code | Meaning |
|---|---|
| 1048 | Column cannot be NULL |
| 1062 | Duplicate entry (UNIQUE / PRIMARY KEY) |
| 1451 | Cannot delete a parent row (FOREIGN KEY, RESTRICT) |
| 1452 | Cannot add a child row (FOREIGN KEY: parent missing) |
| 1644 | Error raised by `SIGNAL` in a stored procedure |
| 3819 | CHECK constraint violated |

## A. Build and schema

| ID | Objective | Steps | Expected result |
|---|---|---|---|
| TC01 | Clean build works | Run 01, 02, 03, 08, 11 on an empty server | No `ERROR` and no `Warning` lines |
| TC02 | All tables exist | `SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA='smart_lab_equipment_db' AND TABLE_TYPE='BASE TABLE';` | The 10 table names |
| TC03 | Every table has a PK | Count `PRIMARY KEY` rows in `information_schema.TABLE_CONSTRAINTS` | 10 |
| TC04 | FKs implement the ER relationships | Query `information_schema.KEY_COLUMN_USAGE WHERE REFERENCED_TABLE_NAME IS NOT NULL` | Exactly the 10 FKs of DESIGN_DECISIONS D-03 |
| TC05 | History cannot be cascaded away | `SELECT DISTINCT DELETE_RULE FROM information_schema.REFERENTIAL_CONSTRAINTS WHERE CONSTRAINT_SCHEMA='smart_lab_equipment_db';` | `RESTRICT` only |
| TC06 | Sample data loaded | Count rows of each table | lab 4, category 6, supplier 4, purchase 7, student 10, staff 4, equipment 20, allocation 20, return 14, maintenance 11 |
| TC07 | Query scripts are valid | Run 04, 05, 06, 07, 09 | No errors or warnings |

## B. Integrity constraints

| ID | Objective | SQL | Expected |
|---|---|---|---|
| TC08 | Valid insert succeeds **(rolls back)** | `START TRANSACTION; INSERT INTO student (student_name, register_number, department, year_of_study, email) VALUES ('Test Student','26BCE1999','CSE',1,'test.student@students.example.edu'); SELECT COUNT(*) FROM student; ROLLBACK;` | 11 |
| TC09 | Duplicate register number **(rejected)** | `INSERT INTO student (student_name, register_number, department, year_of_study, email) VALUES ('Duplicate','24BCE1012','CSE',3,'dup@students.example.edu');` | ERROR 1062 |
| TC10 | Duplicate serial number **(rejected)** | `INSERT INTO equipment (equipment_name, serial_number, category_id, lab_id, purchase_id) VALUES ('Copy','OSC-DS1-0001',1,2,1);` | ERROR 1062 |
| TC11 | Same invoice, same supplier **(rejected)** | `INSERT INTO purchase (supplier_id, purchase_date, invoice_number, total_amount) VALUES (1,'2026-10-01','ASI-2025-0141',1000.00);` | ERROR 1062 |
| TC12 | Same invoice, other supplier allowed **(rolls back)** | Same insert with `supplier_id = 2` inside `START TRANSACTION … ROLLBACK`, then count invoices `ASI-2025-0141` | 2 |
| TC13 | FK: unknown lab **(rejected)** | `INSERT INTO equipment (equipment_name, serial_number, category_id, lab_id, purchase_id) VALUES ('Orphan','TST-0001',1,99,1);` | ERROR 1452 |
| TC14 | FK: unknown student **(rejected)** | `INSERT INTO equipment_allocation (equipment_id, student_id, staff_id, allocation_date, expected_return_date, allocation_status) VALUES (2,999,1,'2026-10-10','2026-10-17','Returned');` | ERROR 1452 |
| TC15 | NOT NULL **(rejected)** | `INSERT INTO equipment (equipment_name, serial_number, category_id, lab_id, purchase_id) VALUES ('No lab','TST-0002',1,NULL,1);` | ERROR 1048 |
| TC16 | CHECK year 1–5 **(rejected)** | `INSERT INTO student (student_name, register_number, department, year_of_study, email) VALUES ('Bad Year','26BCE1998','CSE',7,'bad.year@students.example.edu');` | ERROR 3819 `chk_student_year` |
| TC17 | CHECK amount > 0 **(rejected)** | `INSERT INTO purchase (supplier_id, purchase_date, invoice_number, total_amount) VALUES (1,'2026-10-01','NEG-0001',-500.00);` | ERROR 3819 |
| TC18 | CHECK return date ≥ allocation date **(rejected)** | `INSERT INTO equipment_allocation (equipment_id, student_id, staff_id, allocation_date, expected_return_date, allocation_status) VALUES (2,10,1,'2026-10-10','2026-10-01','Returned');` | ERROR 3819 |
| TC19 | CHECK damaged ≠ available **(rejected)** | `UPDATE equipment SET availability_status='Available' WHERE equipment_id=9;` | ERROR 3819 |
| TC20 | CHECK status domain **(rejected)** | `UPDATE equipment_allocation SET allocation_status='Lost' WHERE allocation_id=1;` | ERROR 3819 |
| TC21 | CHECK completed job has cost **(rejected)** | `INSERT INTO maintenance (equipment_id, staff_id, maintenance_date, maintenance_type, maintenance_status) VALUES (2,1,'2026-10-01','Preventive','Completed');` | ERROR 3819 |
| TC22 | 1:1, second return **(rejected)** | `INSERT INTO equipment_return (allocation_id, return_date, return_condition) VALUES (1,'2026-07-13','Good');` | ERROR 1062 |
| TC23 | Conflicting active allocation **(rejected)** | `INSERT INTO equipment_allocation (equipment_id, student_id, staff_id, allocation_date, expected_return_date, allocation_status) VALUES (1,10,1,'2026-10-10','2026-10-17','Issued');` | ERROR 1062 on `uq_allocation_one_active_per_equipment` |
| TC24 | Past allocations unlimited **(rolls back)** | Insert a `Returned` allocation for equipment 2 inside a transaction; count its allocations; `ROLLBACK` | 2 |

## C. Query results (sample data)

| ID | Objective | Query | Expected |
|---|---|---|---|
| TC25 | Allocations not yet returned | `SELECT a.allocation_id FROM equipment_allocation a LEFT JOIN equipment_return r ON r.allocation_id=a.allocation_id WHERE r.return_id IS NULL;` | 15, 16, 17, 18, 19, 20 |
| TC26 | Aggregation (Q16) | Equipment per lab | Applied Physics 5, Computer Networks 4, Electronics and Circuits 5, Embedded Systems 6 |
| TC27 | Aggregation with WHERE (Q19) | Received purchase total per supplier | 1: 208500.00, 2: 39000.00, 3: 72500.00, 4: 68700.00 |
| TC28 | AVG ignores NULL (Q20) | Average cost per type | Calibration 1400.00, Preventive 500.00, Repair 4816.67 |
| TC29 | HAVING (Q22) | Students with > 2 allocations | Students 1, 2, 7, 9 |
| TC30 | 4-table JOIN (Q31) | Count rows of allocation ⋈ student ⋈ equipment ⋈ lab_staff | 20 (no multiplication) |
| TC31 | Join without multiplication (Q38) | Equipment 1: allocations, maintenance jobs, cost | 2, 2, 4250.00 |
| TC32 | Equipment without maintenance (Q34 = Q44) | NOT EXISTS vs LEFT JOIN anti-join | Both 4, 6, 7, 8, 10, 11, 14, 15, 18, 20 |
| TC33 | Correlated subquery (Q45) | Jobs above own type average | 1, 2, 3, 8 |
| TC34 | Subquery vs average (Q46) | Equipment with total cost above average | 1, 3, 19 |
| TC35 | Benchmark subquery (Q47) | Students above average allocations | 1, 2, 7, 9 |
| TC36 | Views | `COUNT(*)` of the 4 views | 20, 6, 11, 20 |
| TC37 | View + date (Q53) | Overdue on 2026-10-10 | 15, 16, 17 |

## D. Validation queries

| ID | Objective | Steps | Expected |
|---|---|---|---|
| TC38 | Clean data passes | Run `09_validation_queries.sql` | Only the V01 row of zeros and the 3 overdue rows of V15 |
| TC39 | V10 detects drift **(rolls back)** | `START TRANSACTION; UPDATE equipment SET availability_status='Available' WHERE equipment_id=1;` then run V10; `ROLLBACK;` | V10 returns equipment 1 |
| TC40 | V09 detects overlapping loans **(rolls back)** | Insert allocation 900 for equipment 2 on 2026-07-08 (returned 2026-07-09) while allocation 1 (2026-07-06 to 2026-07-12) is out; run V09; `ROLLBACK;` | Pair 1 / 900 reported |

## E. Transactions: allocation and return (changes data)

| ID | Objective | SQL | Expected |
|---|---|---|---|
| TC41 | Successful allocation | `CALL sp_allocate_equipment(15,10,1,'2026-10-10','2026-10-17',@id);` | New allocation `Issued`; equipment 15 `Allocated` |
| TC42 | Conflicting allocation detected | `CALL sp_allocate_equipment(15,3,1,'2026-10-10','2026-10-17',@id);` | ERROR 1644 "equipment 15 is Allocated, not Available" |
| TC43 | Conflict left no partial data | Count `Issued` allocations of equipment 15 | 1 |
| TC44 | Item under maintenance refused | `CALL sp_allocate_equipment(3,10,1,'2026-10-10','2026-10-17',@id);` | ERROR 1644 |
| TC45 | Damaged / unavailable item refused | `CALL sp_allocate_equipment(9,10,1,'2026-10-10','2026-10-17',@id);` | ERROR 1644 |
| TC46 | FK error inside procedure | `CALL sp_allocate_equipment(2,999,1,'2026-10-10','2026-10-17',@id);` | ERROR 1452 |
| TC47 | …fully rolled back | Equipment 2 status; allocations of equipment 2 | `Available`, 1 |
| TC48 | Successful return | `CALL sp_return_equipment(<id from TC41>,'2026-10-10','Good','Returned complete');` | Allocation `Returned`, equipment `Available`, condition `Good`, return row dated 2026-10-10 |
| TC49 | Double return refused | `CALL sp_return_equipment(1,'2026-10-12','Good',NULL);` | ERROR 1644 "already Returned" |
| TC50 | Return before issue refused | `CALL sp_return_equipment(18,'2026-10-01','Good',NULL);` | ERROR 1644 |
| TC51 | Unreturned allocation unchanged | Status and return rows of allocation 18 | `Issued`, 0 |
| TC52 | Damaged return | `CALL sp_return_equipment(19,'2026-10-10','Damaged','Screen cracked');` | Equipment 10 `Unavailable`, `Damaged` |

## F. Concurrency

| ID | Objective | Steps | Expected |
|---|---|---|---|
| TC53 | Simultaneous allocation through the procedure | Session 0 holds `SELECT … FOR UPDATE` on equipment 2 for 2 s. Meanwhile sessions 1 and 2 both call `sp_allocate_equipment(2, …)`. | Exactly one call succeeds and the other gets ERROR 1644; one active allocation |
| TC54 | Simultaneous direct INSERTs | Session A inserts an `Issued` allocation for equipment 5 and waits 2 s before COMMIT. Session B inserts another `Issued` allocation for equipment 5. | B waits, then gets ERROR 1062; A commits |
| TC55 | Consistency after all transactions | Run `09_validation_queries.sql` | Same output as TC38 (no violations) |

## G. History preservation

| ID | Objective | SQL | Expected |
|---|---|---|---|
| TC56 | Student history kept | `DELETE FROM student WHERE student_id=1;` | ERROR 1451 |
| TC57 | Equipment history kept | `DELETE FROM equipment WHERE equipment_id=1;` | ERROR 1451 |
| TC58 | Allocation with return kept | `DELETE FROM equipment_allocation WHERE allocation_id=1;` | ERROR 1451 |
| TC59 | Supplier with purchases kept | `DELETE FROM supplier WHERE supplier_id=1;` | ERROR 1451 |
| TC60 | Records still present | Count original returns (id ≤ 14) and maintenance rows | 14, 11 |

## H. Reset and reproducibility

| ID | Objective | Steps | Expected |
|---|---|---|---|
| TC61 | Reset drops the database | Run `10_reset_database.sql` (the runner uses a copy that targets the **test** database only) | Database no longer listed |
| TC62 | Rebuild from scratch | Run 01, 02, 03, 08, 11 again | No errors or warnings |
| TC63 | Rebuilt data valid | Run `09_validation_queries.sql` | Same output as TC38 |

---

# Review 3 test cases

## I. Maintenance workflow procedures (database, `tests/run_tests.sh`)

These run on the rebuilt test database after TC63.

| ID | Objective | SQL | Expected |
|---|---|---|---|
| TC64 | Start a scheduled job | `CALL sp_start_maintenance(10,'2026-10-10');` | Job 10 `In Progress` dated 2026-10-10; equipment 9 `Under Maintenance` |
| TC65 | Start it again | same call | ERROR 1644 (not Scheduled) |
| TC66 | Work on an issued item | Schedule job 901 for equipment 1 (Allocated), then start it | ERROR 1644 "…currently allocated to a student…" |
| TC67 | Complete a job | `CALL sp_complete_maintenance(10,900.00,'Good','USB connector replaced');` | `Completed`, 900.00; equipment 9 `Good`, `Available` |
| TC68 | Missing cost | `CALL sp_complete_maintenance(8,NULL,'Good',NULL);` | ERROR 1644 |
| TC69 | …nothing changed | Job 8 and equipment 3 | `In Progress`, `Under Maintenance` |
| TC70 | Two jobs on one item | Start job 902 on equipment 3, then complete job 8 | Equipment 3 stays `Under Maintenance` |
| TC71 | Consistency | Run `09_validation_queries.sql` | Same output as TC38 |

## J. Web application (`python -m pytest`, folder `tests/web`)

Before every test, the database `smart_lab_equipment_apptest` is rebuilt from scripts 01, 02, 03, 08, 11 and 12. The app runs with reference date 2026-10-10.

| ID | Objective | Steps | Expected |
|---|---|---|---|
| TA01 | Every page loads | GET 40 URLs (lists, forms, details, filters, search, detail tabs) | HTTP 200 each |
| TA02 | Unknown records | GET `/equipment/999`, `/students/999`, unknown report | HTTP 404 |
| TA03 | Dashboard figures | GET `/` | KPI cards: 11 of 20 available (55%), 6 on loan (3 issued in last 7 days), 3 overdue (oldest 12 days, 50% of loans), 2 in progress · 2 scheduled (₹9,700 committed, ₹10,450 spent); overdue rows Vikram 12 d, Rohan 5 d, Aarav 2 d; loans per month 4/7/5/4; lab utilisation 33/50/40/0%; newest activity = allocation #20 |
| TA04 | Equipment search | Text "oscilloscope", "NET-"; status, lab, category filters | 3, 4, 11, 6 items; multimeters available = 3 serials |
| TA05 | Student search | Name, department, department + year | Matching register numbers only |
| TA06 | SQL injection | Search for `' OR 1=1 --` and a `DROP TABLE` string | 0 rows; student table intact |
| TA07 | Create student | Valid form | Saved (register no. and dept upper-cased); success message |
| TA08 | Validation | Empty name, bad register no., year 9, bad e-mail | HTTP 400, one message per field, nothing saved |
| TA09 | Duplicate register no. | Existing `24BCE1012` | "A student with this register number already exists." |
| TA10 | Update student | Edit year and e-mail | Saved |
| TA11 | Delete student | Student 10 (no history), student 1 (history) | First deleted; second blocked with a message |
| TA12 | Create and edit equipment | New item, then change lab | Item `Available`/`New`; lab updated |
| TA13 | Equipment errors | Duplicate serial; missing lab; condition Damaged | Friendly duplicate message; field errors; nothing saved |
| TA14 | Delete equipment with history | Equipment 1 | Blocked, still present |
| TA15 | Lab CRUD | Add, edit, capacity 0, delete new lab, delete lab 1 | Saved / error / deleted / blocked |
| TA16 | Category CRUD | Add with empty description, duplicate, delete | NULL description, duplicate message, deleted |
| TA17 | Supplier CRUD | Bad phone and e-mail; valid add; delete; delete supplier 1 | Field errors; saved; deleted; blocked |
| TA18 | Staff CRUD | Add, edit, duplicate e-mail, delete | Saved; updated; duplicate message; deleted |
| TA19 | Purchase rules | Valid add; amount 0 + future date; cancel purchase 1 | Saved; field errors; refused (purchase has 4 items) |
| TA20 | Issue | Equipment 15 to student 10 | Allocation #21 `Issued`; equipment `Allocated` |
| TA21 | Issue refused | Equipment 1, 3, 9 | Procedure message naming the status; no new rows |
| TA22 | Issue validation | Due before issue; future issue date; no student | Field errors; no new rows |
| TA23 | Return | Allocation 17, Good; then again | Returned, equipment `Available`; second attempt refused |
| TA24 | Return rules | Return before issue date; return Damaged | Field error; equipment 10 `Unavailable`/`Damaged` |
| TA25 | Maintenance flow | Schedule → start → negative cost → complete | `Scheduled` (still Available) → `In Progress`/`Under Maintenance` → error → `Completed`/`Available` |
| TA26 | Maintenance refusals | Start on an issued item; past date; restart a completed job | Messages; nothing changed |
| TA27 | Consistency | Several issues, returns, repairs via the UI | V06/V07/V08/V10/V11/V12 checks empty |
| TA28 | Reports run | All 8 reports | HTTP 200 and the SQL shown |
| TA29 | Report answers | Overdue, supplier spend, never maintained, frequent borrowers | Same results as Review 2 queries |
| TA30 | CSRF | POST without token | HTTP 400; nothing saved |
| TA31 | HTML escaping | Category named `<script>…` | Rendered escaped |
| TA32 | Validator unit tests | `Form` helpers with good and bad input | Correct values and messages |
| TA40 | Saved views | Equipment tabs All / Available / On loan / Needs attention; with `lab_id=4` | Counts 20/11/6/3; attention = 3 serials; with lab 4: 6/2/2/2; unknown view = all |
| TA41 | Sorting whitelist | `sort=activity&dir=desc`, `sort=lab`, and `sort=equipment_id;DROP TABLE lab` | Newest activity first; lab order equals SQL ORDER BY; bad key falls back to default; lab table intact |
| TA42 | Pagination | `per_page=10` pages 1, 2, 99; `per_page=7` | 10 + 10 distinct rows; "1–10 of 20", "11–20 of 20"; page 99 = last page; 7 not allowed (all 20 shown) |
| TA43 | CSV export | `/equipment/export.csv?view=on_loan&sort=lab` | text/csv attachment `equipment-2026-10-10.csv`; header + 6 rows; OSC-DS1-0001 held by Aarav Menon due 2026-10-08 |
| TA44 | CSV formula injection | Equipment named `=HYPERLINK(...)`, then export | Cell written as `'=HYPERLINK...` |
| TA45 | Global search | `/search?q=menon`, `?q=OSC-DS1`, `?q=' OR 1=1 --` | 1 result; 2 equipment results; 0 results |
| TA46 | Equipment detail tabs | `/equipment/1`, `?tab=loans`, `?tab=maintenance` | Overdue 2 days banner; lifecycle issued, completed, returned, issued, completed, received; "2 loans · 2 maintenance jobs · ₹4,250 spent"; 2 loan rows; total 4,250.00 |
| TA47 | Sidebar counts | Any page | 20 equipment, 4 open jobs, 3 overdue, 10 students, 4 staff, 1 open purchase |
| TA48 | Register-number CHECK | Direct SQL INSERT (bypassing the app) of `24BC1012`, `26bce1997`, `24BCE10120` | ERROR 3819 each; `friendly_error()` returns "Register number must look like 24BCE1012."; still 10 students |

## K. Browser walkthrough (`python tests/browser_walkthrough.py`)

The walkthrough uses a real Chromium browser against a freshly built test database, and saves a screenshot per step to `docs/screenshots/`.

| ID | Journey | Checked on screen |
|---|---|---|
| TB01 | Open the dashboard | "Operations overview", Overdue KPI = 3, overdue student listed |
| TB02 | Search "multimeter", Available | "2 item(s) found." |
| TB03 | Equipment OSC-DS1-0001 | Maintenance remark in history |
| TB04 | Issue with due date before issue date | Field error message; live date check also marked failed |
| TB05 | Correct the date and issue | "Equipment issued (allocation #21)." |
| TB06 | Return allocation 17 | "Return of OSC-DS1-0001 recorded." |
| TB07 | Add student with existing register no. | Duplicate message |
| TB08 | Start scheduled job for MCU-ARD-0009 | "now Under Maintenance" |
| TB09 | Frequent-borrowers report | SQL with HAVING; 4 rows |
| TB10 | Student 24BCE1012 | 4 history rows |
| TB11 | Equipment list: click *Needs attention*, then sort by *Last activity* | Rows = tab count; column marked ascending |
| TB12 | Issue form for DMM-17B-0005: pick student 10, click *2 weeks* | Due date 2026-10-24; 4 checks passed; summary shows the serial |
| TB13 | Phone width (390 px): open the menu | Sidebar hidden, then shown by the toggle; no sideways page scroll |
| TB00 | Open `/equipment/` signed out; wrong password; right password | Sign-in page; "Invalid username or password."; back on the Equipment page |
| TB14 | Sign in as a technician | No "Issue equipment" link; `/allocations/new` shows Error 403; maintenance Start buttons visible |
| TB15 | Sign out from the account menu | "You have signed out."; the dashboard asks to sign in again |
| TB16 | Admin opens activation for 25BCE1103; the student activates, then requests DMM-17B-0006 | "My equipment" with no other students' names; "Request … sent" |
| TB17 | Staff approve the request on Student requests | "approved: equipment issued (allocation #…)" |
| TB18 | Student reloads My equipment, then opens `/equipment/` | DMM-17B-0006 under "On loan to me"; Error 403 |

## L. Register-number format (database, `tests/run_tests.sh`)

The CHECK `chk_student_register_no` in `sql/02_create_tables.sql` enforces the same format as the web form: 2 digits, 3 capital letters, 4 digits (`24BCE1012`). It uses `REGEXP_LIKE(..., 'c')` so the match is case-sensitive under the default collation.

| ID | Objective | SQL | Expected |
|---|---|---|---|
| TC72 | Malformed number **(rejected)** | `INSERT INTO student (student_name, register_number, department, year_of_study, email) VALUES ('Bad Register','24BC1012','CSE',2,'bad.register@students.example.edu');` | ERROR 3819 |
| TC73 | Lower-case number **(rejected)** | Same insert with `'26bce1997'` | ERROR 3819 (proves the check is case-sensitive) |
| TC74 | Constraint declared and data valid | `information_schema.TABLE_CONSTRAINTS` for `student`, plus a count of stored numbers that do not match | `chk_student_register_no,YES,0` |

## M. Sign-in, roles and web security (`python -m pytest`, `tests/web/test_security.py`)

Every test uses fake accounts created in `smart_lab_equipment_apptest` (one per role) with a test-only password.

| ID | Objective | Steps | Expected |
|---|---|---|---|
| TA50 | Successful sign-in | POST `/login` with `next=/equipment/` | 302 to `/equipment/`; session holds the user; CSRF token renewed; `last_login_at` set; cookie `HttpOnly`, `SameSite=Lax` |
| TA51 | No account enumeration | Wrong password; unknown username | Both 401 with the same message; not signed in |
| TA52 | Sign-out | GET `/logout`; POST without token; POST with token | 405; 400; 302 to `/login`, session emptied, dashboard asks to sign in |
| TA53 | Signed-out access | Every protected route | GET: 302 to `/login?next=…`; POST: 401 |
| TA54 | Login CSRF | POST `/login` without token | 400; not signed in |
| TA55 | Complete route map | Compare routes, permission map and sample URLs | Identical sets; permissions equal the documented policy |
| TA56 | Role matrix (×4 roles) | Every route as each role | Allowed: not 401/403; denied: exactly 403 |
| TA57 | Denied writes change nothing | Technician deletes/issues; inventory staff starts maintenance, adds a lab | 403 each; row counts and job status unchanged |
| TA58 | Fail closed | Add a route without a permission rule | 403 |
| TA59 | Interface hides unavailable actions | Pages as technician, inventory staff, lab manager, admin | Buttons/links only for permitted actions; Users link only for admin |
| TA60 | CSRF on state changes | POST without token / with forged token | 400; nothing saved |
| TA61 | Password change | Wrong current password; correct change | 400; 302, other session signed out, new hash verifies |
| TA62 | Deactivation | Admin deactivates the lab manager | Their open session ends; sign-in refused |
| TA63 | Cookie settings | Development and production config | HttpOnly, SameSite=Lax; Secure in production; 8-hour lifetime |
| TA64 | Username lockout | 5 wrong passwords, then the right one | 429; other accounts unaffected |
| TA65 | Address lockout | 20 failures with different usernames | Next sign-in from that address 429 |
| TA66 | Counter reset and pruning | Success after 4 failures; age rows 2 days | Count restarts; rows older than 1 day deleted |
| TA67 | Open redirect (×5) | `next=//evil…`, `https://evil…`, `/\evil…`, `javascript:`, encoded CRLF | Never redirected off the site |
| TA68 | Password storage and policy | Two accounts, same password; weak passwords | `scrypt:` hashes, different salts; short/simple/containing-username refused |
| TA69 | Admin self-lockout | Admin demotes themselves | 400; role unchanged |
| TA69b | Friendly account errors | Duplicate username; link to staff id 999 | 400 with "already exists" / "does not exist", no 500 |
| TA70 | `create-user` command | Create; duplicate; weak password | Created without echoing the password; duplicate and weak refused |
| TA71 | Production configuration (×5) | Missing/short `SECRET_KEY`, `DB_USER=root`, no `DB_PASSWORD`, `COOKIE_SECURE=0` | `ConfigError` naming the setting, never its value |
| TA72 | Headers, size limit, health, error page | Dashboard headers; 70 KB form; `/healthz` up and down; page with the database unavailable | CSP, nosniff, DENY, no-store, no inline handlers; 413; 200/503 JSON; 500 page without internal details |
| TA73 | Migration safety (×2: files 13 and 15) | Run each migration twice on a database with data | Only CREATE statements; every row count unchanged |
| TA74 | Test-database guard | Inspect test settings | Tests and walkthrough target only `smart_lab_equipment_apptest` |

## N. Sign-in migration (database, `tests/run_tests.sh`)

| ID | Objective | Steps | Expected |
|---|---|---|---|
| TC75 | Migration 13 applied in the clean build | Look for the two tables; count accounts | `2,0`: tables exist, no default accounts |
| TC76 | Re-run is safe | Add an account, run `13_app_users.sql` again | Runs without errors or warnings |
| TC77 | …data preserved | Row counts of student, equipment, allocation, maintenance, app_user before and after | Identical |
| TC78 | Account CHECKs | `INSERT` username `'Bad Name'`, role `'superuser'` | ERROR 3819 |

## O. Student accounts and requests (`python -m pytest`, `tests/web/test_student_portal.py`)

Students 1 (Aarav, 24BCE1012) and 2 (Diya, 24BEC1045) have activated test accounts; others are activated in the tests.

| ID | Objective | Steps | Expected |
|---|---|---|---|
| TA80 | Activation | Admin opens activation for student 3; student activates (case-insensitive inputs); tries again | Signed in at `/my/`; scrypt hash stored; second activation refused |
| TA81 | Activation refusals | Wrong e-mail; never opened; expired; deactivated; unknown; weak or mismatched password | Same generic message for the first five; no password stored |
| TA82 | Student sign-in | Register number (any case); wrong password; account not yet activated | `/my/`; 401; 401 |
| TA83 | Own data only | Aarav's and Diya's portals | Own loans and history; no other student's name, register number or e-mail; 11 available items |
| TA84 | Staff pages refused | Every staff route as a student | 403 (dashboard redirects to `/my/`); nothing changed |
| TA85 | Request rules | Valid; duplicate; until < from; past start; > 14 days; no purpose; unavailable item; 4th open request; unknown item | Pending row; 400 with message for each rule; 404 |
| TA86 | Cancel | Diya cancels Aarav's request; Aarav cancels his own; cancels again | 404; Cancelled; "Only a pending request can be cancelled." |
| TA87 | Approve | Technician tries; inventory staff approves; approves again | 403; allocation #21 via the procedure, item Allocated, request Approved; "already been decided" |
| TA88 | Item gone; reject | Two requests for one item; approve both; reject the second with a note | Second refused with the procedure's message and stays Pending; Rejected with note shown to the student |
| TA89 | Admin student sign-in | Open for all; reset an active student; deactivate; bad action; unknown student | 8 pending accounts; reset signs the student out and clears the password; deactivated cannot sign in; 400; 404 |
| TA90 | Student throttling | 5 wrong passwords for 24BCE1012 | 6th attempt 429 |
| TA91 | No collisions | Staff account named `24bce1012` | Refused |
| TA92 | Student password change | Change on one device | Other session signed out |

## P. Student portal migration (database, `tests/run_tests.sh`)

| ID | Objective | Steps | Expected |
|---|---|---|---|
| TC79 | Migration 15 in the clean build | Look for the two tables | `2,0,0`: both exist and are empty |
| TC80 | Re-run is safe | Add an account and a request, run `15_student_portal.sql` again | No errors or warnings |
| TC81 | …data preserved | Row counts before and after | Identical |
| TC82 | One pending request per item | Second pending request, same student and item | ERROR 1062 |
| TC83 | Approved needs an allocation | Mark a request Approved without `allocation_id` | ERROR 3819 |
