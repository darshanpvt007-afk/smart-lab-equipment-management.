# Test Cases

These are the test definitions, 166 in all, and every case is automated under the same ID. Results of the latest run are in `docs/TEST_REPORT.md`.

| IDs | Suite | Run with |
|---|---|---|
| TC01–TC71 | Database tests (A–H Review 2; I Review 3) | `bash tests/run_tests.sh` |
| TA01–TA32 (85 test functions with parameters) | Web application tests (J) | `python -m pytest` |
| TB01–TB10 | Browser walkthrough (K) | `python tests/browser_walkthrough.py` |

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
| TA01 | Every page loads | GET 35 URLs (lists, forms, details, filters) | HTTP 200 each |
| TA02 | Unknown records | GET `/equipment/999`, `/students/999`, unknown report | HTTP 404 |
| TA03 | Dashboard figures | GET `/` | 20 items, 11 available, 6 issued, 3 overdue, 2 under maintenance, 1 unavailable |
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

## K. Browser walkthrough (`python tests/browser_walkthrough.py`)

The walkthrough uses a real Chromium browser against a freshly built test database, and saves a screenshot per step to `docs/screenshots/`.

| ID | Journey | Checked on screen |
|---|---|---|
| TB01 | Open the dashboard | Title, 3 overdue, overdue student listed |
| TB02 | Search "multimeter", Available | "2 item(s) found." |
| TB03 | Equipment OSC-DS1-0001 | Maintenance remark in history |
| TB04 | Issue with due date before issue date | Field error message |
| TB05 | Correct the date and issue | "Equipment issued (allocation #21)." |
| TB06 | Return allocation 17 | "Return of OSC-DS1-0001 recorded." |
| TB07 | Add student with existing register no. | Duplicate message |
| TB08 | Start scheduled job for MCU-ARD-0009 | "now Under Maintenance" |
| TB09 | Frequent-borrowers report | SQL with HAVING; 4 rows |
| TB10 | Student 24BCE1012 | 4 history rows |
