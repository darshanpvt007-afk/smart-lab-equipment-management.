# Test Report — Review 2

| Item | Value |
|---|---|
| Date of run | 2026-10-09 (UTC) |
| DBMS | MySQL **8.0.46** (Ubuntu package `mysql-server-8.0`), default `sql_mode` incl. `STRICT_TRANS_TABLES` and `ONLY_FULL_GROUP_BY` |
| Environment | Temporary Linux cloud sandbox. MySQL was installed there with the student's approval. |
| How executed | `bash tests/run_tests.sh` against the isolated database `smart_lab_equipment_test`, built from the same SQL files |
| Result | **63 passed, 0 failed, 0 not executed**; exit status 0; run time ≈ 6 s |

All results below were **actually executed on MySQL**. No other database engine was used.

**How "Actual" is decided:**
- For value tests, the runner compares the query output *character-for-character* with the expected string.
- For error tests, it checks that the client printed the expected `ERROR <code>`.
- A test is PASS only if the actual output equals the expected output. In the tables below, "Actual" therefore records the observed value, which is identical to "Expected" for every PASS.

**Checking the checker.** The runner's helper functions were checked with three deliberately wrong expectations (negative controls): a wrong count, a statement that succeeds where an error was expected, and a wrong error code. All three were correctly reported as **FAIL**. So the PASS results are not produced by a runner that cannot fail.

**Other manual checks:**
- Every SQL file 01–11 was run with `--show-warnings`. None produced an error or warning. The only messages were two expected `Note 1305` lines, printed by `DROP PROCEDURE IF EXISTS` on the first run of file 11.
- Every query's printed result was compared with the expected result written in its comment. One comment was wrong and was corrected: Q07 returns 4 rows, not 5.
- All SQL in `docs/FACULTY_DEMONSTRATION.md` was run, in order, against a freshly built copy of the database. This found three documentation corrections, which have been applied:
  - the AUTO_INCREMENT value in step 16 is 22, not 21
  - ORDER BY was added to two demo queries so their row order is fixed
  - the DESCRIBE output in step 2 also shows MUL indexes on `equipment_name` and `availability_status`

Full SQL for every test is in `tests/test_cases.md` and `tests/run_tests.sh`.

---

## A. Build and schema

| ID | Objective | Setup | SQL / steps | Expected | Actual | Status |
|---|---|---|---|---|---|---|
| TC01 | Clean build | Empty test DB | Run 01, 02, 03, 08, 11 | No ERROR / Warning | No ERROR / Warning | PASS |
| TC02 | 10 tables exist | After TC01 | `information_schema.TABLES` | 10 table names | equipment, equipment_allocation, equipment_category, equipment_return, lab, lab_staff, maintenance, purchase, student, supplier | PASS |
| TC03 | PK on every table | After TC01 | Count PRIMARY KEY constraints | 10 | 10 | PASS |
| TC04 | FKs match ER relationships | After TC01 | `KEY_COLUMN_USAGE` | 10 FKs of D-03 | 10 FKs, parents as specified | PASS |
| TC05 | No cascading deletes | After TC01 | `REFERENTIAL_CONSTRAINTS.DELETE_RULE` | RESTRICT | RESTRICT | PASS |
| TC06 | Sample row counts | After TC01 | Count each table | 4,6,4,7,10,4,20,20,14,11 | 4,6,4,7,10,4,20,20,14,11 | PASS |
| TC07 | Query scripts valid | After TC01 | Run 04, 05, 06, 07, 09 | No ERROR / Warning | No ERROR / Warning | PASS |

## B. Integrity constraints

| ID | Objective | Setup | SQL / steps | Expected | Actual | Status |
|---|---|---|---|---|---|---|
| TC08 | Valid insert | Sample data | INSERT student in a transaction, count, ROLLBACK | 11 | 11 | PASS |
| TC09 | Duplicate register number | Sample data | INSERT `24BCE1012` | ERROR 1062 | ERROR 1062 | PASS |
| TC10 | Duplicate serial number | Sample data | INSERT `OSC-DS1-0001` | ERROR 1062 | ERROR 1062 | PASS |
| TC11 | Duplicate invoice, same supplier | Sample data | INSERT supplier 1, `ASI-2025-0141` | ERROR 1062 | ERROR 1062 | PASS |
| TC12 | Same invoice, other supplier | Sample data | INSERT supplier 2, same invoice (rolled back) | 2 | 2 | PASS |
| TC13 | FK: unknown lab | Sample data | INSERT equipment `lab_id=99` | ERROR 1452 | ERROR 1452 | PASS |
| TC14 | FK: unknown student | Sample data | INSERT allocation `student_id=999` | ERROR 1452 | ERROR 1452 | PASS |
| TC15 | NOT NULL | Sample data | INSERT equipment `lab_id=NULL` | ERROR 1048 | ERROR 1048 | PASS |
| TC16 | CHECK year | Sample data | INSERT student year 7 | ERROR 3819 | ERROR 3819 | PASS |
| TC17 | CHECK amount | Sample data | INSERT purchase −500.00 | ERROR 3819 | ERROR 3819 | PASS |
| TC18 | CHECK dates | Sample data | INSERT allocation due before issue | ERROR 3819 | ERROR 3819 | PASS |
| TC19 | CHECK damaged ≠ available | Equipment 9 is Damaged | UPDATE to Available | ERROR 3819 | ERROR 3819 | PASS |
| TC20 | CHECK status domain | Sample data | UPDATE status 'Lost' | ERROR 3819 | ERROR 3819 | PASS |
| TC21 | CHECK completed cost | Sample data | INSERT Completed maintenance, no cost | ERROR 3819 | ERROR 3819 | PASS |
| TC22 | 1:1 return | Allocation 1 has a return | INSERT second return | ERROR 1062 | ERROR 1062 | PASS |
| TC23 | One active allocation | Equipment 1 is Issued | INSERT another Issued allocation | ERROR 1062 | ERROR 1062 | PASS |
| TC24 | Past allocations unlimited | Sample data | INSERT Returned allocation, equipment 2 (rolled back) | 2 | 2 | PASS |

## C. Query results

| ID | Objective | Setup | SQL / steps | Expected | Actual | Status |
|---|---|---|---|---|---|---|
| TC25 | Unreturned allocations | Sample data | LEFT JOIN … `IS NULL` | 15,16,17,18,19,20 | 15,16,17,18,19,20 | PASS |
| TC26 | Equipment per lab (Q16) | Sample data | COUNT / GROUP BY | Physics 5, Networks 4, Electronics 5, Embedded 6 | same | PASS |
| TC27 | Spend per supplier (Q19) | Sample data | SUM, WHERE Received | 1:208500.00, 2:39000.00, 3:72500.00, 4:68700.00 | same | PASS |
| TC28 | AVG ignores NULL (Q20) | Sample data | AVG per type | 1400.00, 500.00, 4816.67 | same | PASS |
| TC29 | HAVING (Q22) | Sample data | COUNT > 2 | 1,2,7,9 | 1,2,7,9 | PASS |
| TC30 | 4-table join (Q31) | Sample data | COUNT of join | 20 | 20 | PASS |
| TC31 | No row multiplication (Q38) | Sample data | Derived-table join, equipment 1 | 2,2,4250.00 | 2,2,4250.00 | PASS |
| TC32 | No maintenance history (Q34 = Q44) | Sample data | NOT EXISTS vs LEFT JOIN | both 4,6,7,8,10,11,14,15,18,20 | same | PASS |
| TC33 | Correlated subquery (Q45) | Sample data | Cost > own type average | 1,2,3,8 | 1,2,3,8 | PASS |
| TC34 | Above-average total cost (Q46) | Sample data | HAVING vs derived AVG | 1,3,19 | 1,3,19 | PASS |
| TC35 | Above-average borrowers (Q47) | Sample data | HAVING vs benchmark | 1,2,7,9 | 1,2,7,9 | PASS |
| TC36 | View row counts | Sample data | COUNT of 4 views | 20,6,11,20 | 20,6,11,20 | PASS |
| TC37 | Overdue via view (Q53) | Ref. date 2026-10-10 | Filter view | 15,16,17 | 15,16,17 | PASS |

## D. Validation queries

| ID | Objective | Setup | SQL / steps | Expected | Actual | Status |
|---|---|---|---|---|---|---|
| TC38 | Clean data passes | Sample data | Run file 09 | V01 all zeros + V15 rows 15, 16, 17; nothing else | identical | PASS |
| TC39 | V10 catches drift | Equipment 1 set Available in a transaction | V10, then ROLLBACK | equipment 1 | 1 | PASS |
| TC40 | V09 catches overlap | Overlapping allocation 900 inserted in a transaction | V09, then ROLLBACK | 1/900 | 1/900 | PASS |

## E. Transactions

| ID | Objective | Setup | SQL / steps | Expected | Actual | Status |
|---|---|---|---|---|---|---|
| TC41 | Successful allocation | Equipment 15 Available | `CALL sp_allocate_equipment(15,10,1,…)` | Issued, Allocated, student 10 | Issued, Allocated, 10 | PASS |
| TC42 | Conflict detected | After TC41 | Allocate equipment 15 again | ERROR 1644 | ERROR 1644 "…equipment 15 is Allocated, not Available" | PASS |
| TC43 | No partial data | After TC42 | Count Issued, equipment 15 | 1 | 1 | PASS |
| TC44 | Under maintenance refused | Equipment 3 | CALL allocate | ERROR 1644 | ERROR 1644 | PASS |
| TC45 | Damaged refused | Equipment 9 | CALL allocate | ERROR 1644 | ERROR 1644 | PASS |
| TC46 | FK error in procedure | Student 999 | CALL allocate equipment 2 | ERROR 1452 | ERROR 1452 | PASS |
| TC47 | Rolled back | After TC46 | Equipment 2 status, allocation count | Available,1 | Available,1 | PASS |
| TC48 | Successful return | Allocation from TC41 | `CALL sp_return_equipment(…,'Good')` | Returned, Available, Good, 2026-10-10 | same | PASS |
| TC49 | Double return refused | Allocation 1 already returned | CALL return | ERROR 1644 | ERROR 1644 | PASS |
| TC50 | Return before issue refused | Allocation 18 issued 2026-10-05 | Return dated 2026-10-01 | ERROR 1644 | ERROR 1644 | PASS |
| TC51 | Unreturned allocation unchanged | After TC50 | Status, return rows of 18 | Issued,0 | Issued,0 | PASS |
| TC52 | Damaged return | Allocation 19 (equipment 10) | Return as Damaged | Unavailable,Damaged | Unavailable,Damaged | PASS |

## F. Concurrency

| ID | Objective | Setup | SQL / steps | Expected | Actual | Status |
|---|---|---|---|---|---|---|
| TC53 | Simultaneous procedure calls | Session 0 locks equipment 2 for 2 s | Sessions 1 and 2 call allocate on equipment 2 in parallel | 1 OK, 1 ERROR 1644, 1 active allocation | 1 OK, 1 ERROR 1644, 1 active | PASS |
| TC54 | Simultaneous direct INSERTs | Session A holds an open insert for 2 s | Session B inserts conflicting Issued row | A OK, B ERROR 1062 | A OK, B ERROR 1062 | PASS |
| TC55 | Consistent after transactions | After TC41–TC54 | Run file 09 | Same as TC38 | identical | PASS |

## G. History preservation

| ID | Objective | Setup | SQL / steps | Expected | Actual | Status |
|---|---|---|---|---|---|---|
| TC56 | Student with history | Student 1 has allocations | DELETE student 1 | ERROR 1451 | ERROR 1451 | PASS |
| TC57 | Equipment with history | Equipment 1 | DELETE | ERROR 1451 | ERROR 1451 | PASS |
| TC58 | Allocation with return | Allocation 1 | DELETE | ERROR 1451 | ERROR 1451 | PASS |
| TC59 | Supplier with purchases | Supplier 1 | DELETE | ERROR 1451 | ERROR 1451 | PASS |
| TC60 | History intact | After TC56–TC59 | Count returns ≤ 14, maintenance | 14,11 | 14,11 | PASS |

## H. Reset and reproducibility

| ID | Objective | Setup | SQL / steps | Expected | Actual | Status |
|---|---|---|---|---|---|---|
| TC61 | Reset drops database | Test DB only | Run file 10 (retargeted copy) | Database absent | absent (0 schemas) | PASS |
| TC62 | Rebuild | After TC61 | Run 01, 02, 03, 08, 11 | No ERROR / Warning | No ERROR / Warning | PASS |
| TC63 | Rebuilt data valid | After TC62 | Run file 09 | Same as TC38 | identical | PASS |

---

## Raw output of the final run

```
MySQL version : 8.0.46-0ubuntu0.24.04.4
Test database : smart_lab_equipment_test (the development database smart_lab_equipment_db is not used)
---------------------------------------------------------------------
PASS  TC01  Clean build: 01, 02, 03, 08, 11 run without errors or warnings
PASS  TC02  All 10 base tables exist
PASS  TC03  Every table has a PRIMARY KEY
PASS  TC04  All 10 foreign keys declared with the right parent tables
PASS  TC05  Foreign keys use ON DELETE RESTRICT (history cannot be cascaded away)
PASS  TC06  Sample data row counts (lab..maintenance)
PASS  TC07  Query scripts 04, 05, 06, 07, 09 run without errors or warnings
PASS  TC08  Valid INSERT of a new student succeeds (rolled back afterwards)
PASS  TC09  Duplicate student register_number rejected (UNIQUE)
PASS  TC10  Duplicate equipment serial_number rejected (UNIQUE)
PASS  TC11  Duplicate invoice number from the SAME supplier rejected
PASS  TC12  Same invoice number from a DIFFERENT supplier is allowed (rolled back)
PASS  TC13  Equipment with a non-existent lab rejected (FOREIGN KEY)
PASS  TC14  Allocation for a non-existent student rejected (FOREIGN KEY)
PASS  TC15  NULL lab_id rejected (NOT NULL)
PASS  TC16  year_of_study = 7 rejected (CHECK)
PASS  TC17  Negative purchase amount rejected (CHECK)
PASS  TC18  Expected return date before allocation date rejected (CHECK)
PASS  TC19  Damaged equipment cannot be marked Available (CHECK)
PASS  TC20  Invalid allocation_status 'Lost' rejected (CHECK)
PASS  TC21  Completed maintenance without a cost rejected (CHECK)
PASS  TC22  Second return for the same allocation rejected (1:1, UNIQUE)
PASS  TC23  Second ACTIVE allocation of the same equipment rejected (functional UNIQUE index)
PASS  TC24  Many RETURNED allocations of the same equipment are still allowed (rolled back)
PASS  TC25  Unreturned allocations (LEFT JOIN, no return row)
PASS  TC26  Aggregation: equipment count per lab (Q16)
PASS  TC27  Aggregation: received purchase expenditure per supplier (Q19)
PASS  TC28  Aggregation: average cost per maintenance type, NULLs ignored (Q20)
PASS  TC29  HAVING: students with more than 2 allocations (Q22)
PASS  TC30  JOIN: 4-table allocation register returns one row per allocation (Q31)
PASS  TC31  JOIN: pre-aggregated counts avoid row multiplication for equipment 1 (Q38)
PASS  TC32  Equipment without maintenance: NOT EXISTS (Q44) = LEFT JOIN anti-join (Q34)
PASS  TC33  Correlated subquery: jobs above their type's average cost (Q45)
PASS  TC34  Subquery: equipment with total maintenance cost above average (Q46)
PASS  TC35  Subquery: students above the average allocation benchmark (Q47)
PASS  TC36  Views exist and return the expected row counts
PASS  TC37  View: overdue allocations on 2026-10-10 (Q53)
PASS  TC38  Validation checks V01-V14, V16 find no violations; V15 lists the 3 overdue loans
PASS  TC39  Validation V10 detects availability drift (equipment 1 wrongly set Available)
PASS  TC40  Validation V09 detects overlapping loan periods of one equipment item
PASS  TC41  sp_allocate_equipment issues an Available item and marks it Allocated
PASS  TC42  sp_allocate_equipment refuses an item that is already Allocated
PASS  TC43  ...and the refused call left exactly one active allocation for that item
PASS  TC44  sp_allocate_equipment refuses an item Under Maintenance (equipment 3)
PASS  TC45  sp_allocate_equipment refuses a Damaged/Unavailable item (equipment 9)
PASS  TC46  sp_allocate_equipment with an unknown student fails with the FK error...
PASS  TC47  ...and is fully rolled back (equipment 2 still Available, no new allocation)
PASS  TC48  sp_return_equipment records the return and makes the item Available
PASS  TC49  sp_return_equipment refuses to return the same allocation twice
PASS  TC50  sp_return_equipment refuses a return dated before the allocation
PASS  TC51  ...and allocation 18 is unchanged (still Issued, no return row)
PASS  TC52  Returning an item Damaged makes it Unavailable with condition Damaged
PASS  TC53  Concurrent sp_allocate_equipment on one item: exactly one succeeds
PASS  TC54  Concurrent direct INSERTs of active allocations: second is rejected (1062)
PASS  TC55  After all procedure calls, validation still finds no violations
PASS  TC56  Deleting a student with allocation history is blocked (RESTRICT)
PASS  TC57  Deleting equipment with allocation/maintenance history is blocked
PASS  TC58  Deleting an allocation that has a return record is blocked
PASS  TC59  Deleting a supplier with purchases is blocked
PASS  TC60  All 14 original returns and 11 maintenance records still present
PASS  TC61  Reset script (run on the TEST database only) drops the database
PASS  TC62  Rebuild after reset succeeds (reproducible from a clean server)
PASS  TC63  Rebuilt database passes validation again
---------------------------------------------------------------------
Passed: 63   Failed: 0   Total: 63
```

## Not tested / limitations

- **Other MySQL versions.** Only MySQL 8.0.46 was tested. Versions older than 8.0.16 ignore CHECK constraints, and versions older than 8.0.13 cannot create the functional index (TROUBLESHOOTING.md). MariaDB was not tested.
- **Windows / macOS.** The SQL is platform-independent, but the shell commands in the README were executed only on Linux. The bash runner needs Git Bash or WSL on Windows.
- **MySQL Workbench.** Not used here; it was not available in the sandbox. The `DELIMITER` handling of file 11 in Workbench is described from MySQL documentation, not from a test.
- **Concurrency coverage.** The concurrency tests prove the rule for two simultaneous sessions on one item. They are not a load test.
