# smart-lab-equipment-management.
Smart Laboratory Equipment Inventory, Allocation and Maintenance Management System

**Database Systems project. Review 2: Database Design & SQL Implementation.**

A MySQL database that records a college's laboratories, equipment, categories, suppliers, purchases, students, lab staff, equipment allocations, returns and maintenance. It is a direct implementation of the ER design approved in Review 1.

---

## 1. Scope of Review 2

| Required by the review instructions | Where |
|---|---|
| Conversion of the ER diagram into relational tables | `sql/02_create_tables.sql`, `docs/RELATIONAL_SCHEMA.md` |
| Primary keys and foreign keys | `sql/02_create_tables.sql` |
| Integrity constraints | `sql/02_create_tables.sql` (NOT NULL, UNIQUE, CHECK, FK), `sql/09_validation_queries.sql` |
| Table creation | `sql/01_create_database.sql`, `sql/02_create_tables.sql` |
| Sample data insertion | `sql/03_insert_sample_data.sql` |
| SELECT, WHERE, ORDER BY | `sql/04_basic_queries.sql` |
| GROUP BY, HAVING, aggregate functions | `sql/05_aggregate_queries.sql` |
| JOIN | `sql/06_join_queries.sql` |
| Subqueries | `sql/07_subqueries.sql` |
| Views | `sql/08_create_views.sql` |

In addition:
- **Transactions:** `sql/11_transaction_procedures.sql` holds atomic allocation and return procedures that are safe under concurrency.
- **Tests:** 63 automated tests (`tests/`).
- **Faculty demonstration guide:** includes viva answers (`docs/FACULTY_DEMONSTRATION.md`).

## 2. Technology

| | |
|---|---|
| DBMS | **MySQL 8.0.16 or newer** (needed for enforced CHECK constraints and functional indexes). Tested on MySQL 8.0.46. |
| Database | `smart_lab_equipment_db`, character set `utf8mb4`, collation `utf8mb4_0900_ai_ci`, engine InnoDB |
| Client | `mysql` command-line client (MySQL Workbench also works) |
| Tests | `bash` + `mysql` client. No other dependencies. |

## 3. Directory structure

```
.
├── README.md
├── docs/
│   ├── REVIEW2_IMPLEMENTATION_PLAN.md   requirement → file → test mapping
│   ├── RELATIONAL_SCHEMA.md             every table, column, key and constraint
│   ├── DESIGN_DECISIONS.md              why each decision was made (D-01 … D-19)
│   ├── NORMALIZATION.md                 1NF / 2NF / 3NF with this schema's FDs
│   ├── SQL_QUERY_CATALOG.md             Q01–Q55, V01–V16, views, procedures
│   ├── TEST_REPORT.md                   results of the latest test run
│   ├── FACULTY_DEMONSTRATION.md         15-step demo script + viva Q&A
│   └── TROUBLESHOOTING.md               common errors and fixes
├── sql/
│   ├── 01_create_database.sql
│   ├── 02_create_tables.sql
│   ├── 03_insert_sample_data.sql
│   ├── 04_basic_queries.sql             Q01–Q15
│   ├── 05_aggregate_queries.sql         Q16–Q27
│   ├── 06_join_queries.sql              Q28–Q38
│   ├── 07_subqueries.sql                Q39–Q49
│   ├── 08_create_views.sql              4 views + Q50–Q55
│   ├── 09_validation_queries.sql        V01–V16
│   ├── 10_reset_database.sql            DESTRUCTIVE: drops the database
│   └── 11_transaction_procedures.sql    sp_allocate_equipment, sp_return_equipment
└── tests/
    ├── README.md
    ├── test_cases.md                    TC01–TC63 definitions
    └── run_tests.sh                     automated runner (uses a separate test DB)
```

## 4. Database design summary

The design has ten tables, one per Review 1 entity. **Equipment** is the central table.

```
supplier ──1:N── purchase ──1:N── equipment ──N:1── equipment_category
                                    │    └──N:1── lab
                    ┌───────────────┼──────────────────┐
                   1:N             1:N                1:N
                    │               │                  │
      equipment_allocation ──N:1── student        maintenance ──N:1── lab_staff
             │      └──N:1── lab_staff (issued by)
            1:1 (optional)
             │
      equipment_return
```

| Design point | How it is implemented |
|---|---|
| Keys and relationships | Integer `AUTO_INCREMENT` primary keys. Each 1:N relationship is a `NOT NULL` foreign key on the N side. Allocation→Return (1:1) is a `UNIQUE NOT NULL` foreign key in `equipment_return`. |
| Business identifiers | `register_number`, `serial_number`, `(supplier_id, invoice_number)` and e-mails are `UNIQUE`. |
| Value domains | CHECK constraints restrict statuses, conditions, years, amounts and date order. |
| History preservation | All foreign keys are `ON DELETE RESTRICT`, so allocation, return, purchase and maintenance history cannot be deleted by cascade. |
| One item, one borrower | A functional UNIQUE index allows only one active ('Issued') allocation per equipment item. It also holds under concurrent transactions. |
| Availability | `availability_status` is a stored Review 1 attribute. It is changed atomically by the procedures in file 11 and audited by validation queries V10–V12. |

Full details: `docs/RELATIONAL_SCHEMA.md` and `docs/DESIGN_DECISIONS.md`.

## 5. Installation prerequisites

1. Install **MySQL Server 8.0** (Community Edition): <https://dev.mysql.com/downloads/mysql/>
   - Windows: use the MySQL Installer and note the root password.
   - Ubuntu: `sudo apt install mysql-server`
   - macOS: `brew install mysql`
2. Start the server and check that it responds:
   ```bash
   mysql --version          # should show 8.0.x
   mysqladmin -u root -p ping
   ```

**Credentials:** never write a password into the scripts. Use one of these:
- `-p` with no value, so `mysql` prompts for the password
- a saved, encrypted login path:
  ```bash
  mysql_config_editor set --login-path=smartlab --host=localhost --user=root --password
  mysql --login-path=smartlab      # then use this instead of "mysql -u root -p"
  ```
- on Ubuntu, `sudo mysql` (socket authentication for root)

## 6. Build the database

Run these from the project folder, in this order. Each command asks for the MySQL password.

```bash
mysql -u root -p < sql/01_create_database.sql        # 1. database (utf8mb4)
mysql -u root -p < sql/02_create_tables.sql          # 2. ten tables + constraints
mysql -u root -p < sql/03_insert_sample_data.sql     # 3. sample data (one transaction)
mysql -u root -p < sql/08_create_views.sql           # 4. views (+ demo queries)
mysql -u root -p < sql/11_transaction_procedures.sql # 5. stored procedures
```

Or, inside the `mysql` client started from the project folder:

```sql
SOURCE sql/01_create_database.sql;
SOURCE sql/02_create_tables.sql;
SOURCE sql/03_insert_sample_data.sql;
SOURCE sql/08_create_views.sql;
SOURCE sql/11_transaction_procedures.sql;
```

On Windows Command Prompt, use the full path if needed: `mysql -u root -p < C:\path\to\project\sql\01_create_database.sql`. In PowerShell the `<` redirection does not work; use `Get-Content sql\01_create_database.sql | mysql -u root -p`, or use `SOURCE` inside the client.

`03` prints the row count of every table: lab 4, equipment_category 6, supplier 4, purchase 7, student 10, lab_staff 4, equipment 20, equipment_allocation 20, equipment_return 14, maintenance 11.

## 7. Run the query scripts

The `-t` option prints results as tables.

```bash
mysql -u root -p -t < sql/04_basic_queries.sql       # Q01–Q15  SELECT / WHERE / ORDER BY
mysql -u root -p -t < sql/05_aggregate_queries.sql   # Q16–Q27  aggregates, GROUP BY, HAVING
mysql -u root -p -t < sql/06_join_queries.sql        # Q28–Q38  INNER / LEFT / multi-table JOIN
mysql -u root -p -t < sql/07_subqueries.sql          # Q39–Q49  subqueries
mysql -u root -p -t < sql/08_create_views.sql        # views + Q50–Q55
mysql -u root -p -t < sql/09_validation_queries.sql  # V01–V16  integrity checks
```

Each query has a comment giving its ID, purpose and expected result. `docs/SQL_QUERY_CATALOG.md` lists them all.

Date-based queries (overdue loans) use the fixed reference date `@ref_date = '2026-10-10'` so that results are repeatable. Replace it with `CURDATE()` for live use.

## 8. Inspect the tables, keys and constraints

```sql
USE smart_lab_equipment_db;
SHOW TABLES;                                   -- 10 tables + 4 views
DESCRIBE equipment;                            -- columns, PRI / UNI / MUL keys
SHOW CREATE TABLE equipment_allocation\G       -- full definition incl. FKs and CHECKs
SHOW INDEX FROM equipment_allocation;

-- primary / unique / foreign keys and checks of every table
SELECT TABLE_NAME, CONSTRAINT_NAME, CONSTRAINT_TYPE
FROM information_schema.TABLE_CONSTRAINTS
WHERE TABLE_SCHEMA = 'smart_lab_equipment_db'
ORDER BY TABLE_NAME, CONSTRAINT_TYPE;

-- every foreign key and the table it references
SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = 'smart_lab_equipment_db' AND REFERENCED_TABLE_NAME IS NOT NULL;

-- CHECK constraint rules
SELECT CONSTRAINT_NAME, CHECK_CLAUSE
FROM information_schema.CHECK_CONSTRAINTS
WHERE CONSTRAINT_SCHEMA = 'smart_lab_equipment_db';
```

## 9. Test the views

```sql
SHOW FULL TABLES WHERE Table_type = 'VIEW';
SELECT * FROM vw_equipment_inventory;          -- 20 rows
SELECT * FROM vw_outstanding_allocations;      -- 6 rows
SELECT * FROM vw_maintenance_history;          -- 11 rows
SELECT * FROM vw_allocation_history WHERE register_number = '24BCE1012';  -- 4 rows
```

## 10. Allocate and return equipment (transactions)

```sql
CALL sp_allocate_equipment(15, 10, 1, '2026-10-10', '2026-10-17', @id);  -- equipment, student, staff, date, due
SELECT @id;
CALL sp_return_equipment(@id, '2026-10-10', 'Good', 'Returned complete');
```

These calls **change the data**. Reset and rebuild (section 12) to return to the documented sample state.

## 11. Run the automated tests

```bash
bash tests/run_tests.sh
# or, with a saved login path:
MYSQL_CMD="mysql --login-path=smartlab" bash tests/run_tests.sh
```

The runner builds and tests a **separate** database, `smart_lab_equipment_test`, and drops it at the end. Your development database is not touched. Expected last line: `Passed: 63   Failed: 0   Total: 63`. See `tests/README.md` and `docs/TEST_REPORT.md`.

## 12. Reset the development database (destructive)

`sql/10_reset_database.sql` runs `DROP DATABASE smart_lab_equipment_db`. **All tables, views, procedures and data are permanently deleted.** No other script runs it. Use it only on purpose:

```bash
# optional backup first
mysqldump -u root -p --routines smart_lab_equipment_db > backup.sql
# reset, then rebuild with the commands in section 6
mysql -u root -p < sql/10_reset_database.sql
```

## 13. Common errors

| Error | Usual cause | Fix |
|---|---|---|
| `ERROR 2002 / 2003 Can't connect` | Server not running | Start the MySQL service |
| `ERROR 1045 Access denied` | Wrong user or password | Check the credentials; on Ubuntu try `sudo mysql` |
| `ERROR 1046 No database selected` | Statement typed outside the scripts | `USE smart_lab_equipment_db;` |
| `ERROR 1050 Table already exists` | `02` run twice | Reset (section 12), then rebuild |
| `ERROR 1062 Duplicate entry` | `03` run twice, or a duplicate unique value | Do not reload the data; use a new value |
| `ERROR 1452 / 1451` | Foreign key: missing parent / parent still has history | Insert the parent first; history rows block deletes by design |
| `ERROR 3819 Check constraint` | Value outside the allowed domain | See the constraint name in docs/RELATIONAL_SCHEMA.md |
| `ERROR 1644 Allocation refused …` | Business rule in a procedure | Read the message; nothing was changed |

More problems and fixes: `docs/TROUBLESHOOTING.md`.

## 14. Status: implemented vs. Review 3

**Implemented and tested in Review 2:**
- the 10-table schema with all keys and constraints
- realistic sample data
- 55 demonstration queries
- 4 views
- 16 validation checks
- 2 transaction procedures
- 63 automated tests (all passing on MySQL 8.0.46)
- full documentation

**Planned for Review 3:**
- simple user interface
- application database connectivity
- CRUD screens
- search and retrieval forms
- input validation in the UI
- calling the important queries and procedures from the application
- a maintenance start/complete procedure that updates availability
- overdue and maintenance reminder screens, built on Q53 / V15 / V16
- final test cases, final report and presentation
