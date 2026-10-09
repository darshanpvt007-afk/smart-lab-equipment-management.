# Troubleshooting

## Running the scripts in the right order

| Order | Script | Needs |
|---|---|---|
| 1 | `01_create_database.sql` | MySQL server running |
| 2 | `02_create_tables.sql` | 01 (the database must exist) |
| 3 | `03_insert_sample_data.sql` | 02 (tables must exist and be empty) |
| 4 | `08_create_views.sql` | 02 |
| 5 | `11_transaction_procedures.sql` | 02 |
| 6 | `12_maintenance_procedures.sql` | 02 (added in Review 3; the web app needs it) |
| any time after 3 | `04`–`07`, `09` | data loaded (08 is also needed for Q50–Q55) |
| only deliberately | `10_reset_database.sql` | — (**destroys the database**) |

---

## MySQL service not running

**Symptom**
```
ERROR 2002 (HY000): Can't connect to local MySQL server through socket '/var/run/mysqld/mysqld.sock'
ERROR 2003 (HY000): Can't connect to MySQL server on 'localhost:3306'
```

**Fix:** start the server.

| OS | Command |
|---|---|
| Ubuntu / Debian | `sudo systemctl start mysql`, or `sudo service mysql start` |
| macOS (Homebrew) | `brew services start mysql` |
| Windows | Services → **MySQL80** → Start, or `net start MySQL80` in an Administrator prompt |

Check that it is up with `mysqladmin -u root -p ping`, which should print `mysqld is alive`.

## Access denied

**Symptom:** `ERROR 1045 (28000): Access denied for user 'root'@'localhost' (using password: YES)`

- Check the user name and password. Use `-p` without a value so MySQL prompts for the password; never write it into the scripts.
- On Ubuntu, a fresh `root` account often uses socket authentication. Use `sudo mysql` instead.
- It is better to create a dedicated account once:
  ```sql
  CREATE USER 'labadmin'@'localhost' IDENTIFIED BY 'choose-a-password';
  GRANT ALL PRIVILEGES ON smart_lab_equipment_db.* TO 'labadmin'@'localhost';
  -- only needed for the automated tests:
  GRANT ALL PRIVILEGES ON smart_lab_equipment_test.* TO 'labadmin'@'localhost';
  ```
  Then store the login once: `mysql_config_editor set --login-path=smartlab --user=labadmin --password`.

If you see `ERROR 1044: Access denied ... to database`, the account lacks privileges on that database. Grant them as shown above.

## Database not selected

**Symptom:** `ERROR 1046 (3D000): No database selected`

Every script starts with `USE smart_lab_equipment_db;`. This error therefore means a statement was typed or pasted by hand. Run `USE smart_lab_equipment_db;` first, or prefix table names (`smart_lab_equipment_db.equipment`).

`ERROR 1049 (42000): Unknown database 'smart_lab_equipment_db'` means `01_create_database.sql` has not been run, or the database was reset.

## Table already exists

**Symptom:** `ERROR 1050 (42S01): Table 'lab' already exists` when running `02_create_tables.sql`.

The tables were already created. `02` deliberately does not drop anything. To start over, back up anything you need, run `10_reset_database.sql`, then run 01 → 02 → 03 → 08 → 11.

## Foreign key constraint failures

**Symptom on INSERT / UPDATE:**
```
ERROR 1452 (23000): Cannot add or update a child row: a foreign key constraint fails (... CONSTRAINT `fk_equipment_lab` ...)
```
The value refers to a parent row that does not exist (e.g. `lab_id = 99`). Insert the parent first, or use an existing ID:

```sql
SELECT lab_id, lab_name FROM lab;
```

**Symptom on DELETE:**
```
ERROR 1451 (23000): Cannot delete or update a parent row: a foreign key constraint fails
```
This is intended. History (allocations, returns, maintenance, purchases) must not be lost, so all foreign keys use `ON DELETE RESTRICT`. Do not delete students, equipment or suppliers that have history.

**Symptom while loading `03`:** a 1452 error means `03` was edited and a parent row was removed or renumbered. Parents are inserted before children in this order: lab, category, supplier, student, staff, purchase, equipment, allocation, return, maintenance.

## Duplicate key violations

**Symptom:** `ERROR 1062 (23000): Duplicate entry '24BCE1012' for key 'student.uq_student_register_no'`

The value of a UNIQUE column already exists. Common causes:

| Key in the message | Meaning |
|---|---|
| `PRIMARY` while running `03` a second time | The sample data is already loaded. Do not run `03` twice. Reset and rebuild if needed. |
| `uq_student_register_no`, `uq_equipment_serial_number`, `uq_student_email`, … | That register number, serial number or e-mail is already used. |
| `uq_purchase_supplier_invoice` | That supplier already has a purchase with this invoice number. |
| `uq_return_allocation` | The allocation already has a return (an allocation can be returned only once). |
| `uq_allocation_one_active_per_equipment` | The equipment is already issued to someone. Return it first. |

## CHECK constraint violations

**Symptom:** `ERROR 3819 (HY000): Check constraint 'chk_student_year' is violated.`

The value is outside the allowed domain. The constraint name tells you which rule failed (see `docs/RELATIONAL_SCHEMA.md`). Common cases:

| Constraint | Rule |
|---|---|
| `chk_equipment_availability` | Status must be one of `Available`, `Allocated`, `Under Maintenance`, `Unavailable` (exact spelling; case is not significant) |
| `chk_equipment_damaged_not_available` | A Damaged item cannot be Available |
| `chk_allocation_dates` | Expected return date must be on or after the allocation date |
| `chk_maintenance_completed_cost` | A Completed maintenance job needs a cost |
| `chk_*_contact` / `chk_*_email` | Phone must be 10–14 digits (optional `+`); e-mail must look like `name@domain.tld` |

MySQL **older than 8.0.16** parses CHECK constraints but silently ignores them, so invalid rows would be accepted. Check your version with `SELECT VERSION();`.

## Errors from the stored procedures

**Symptom:** `ERROR 1644 (45000): Allocation refused: equipment 1 is Allocated, not Available`

These are business-rule messages raised with `SIGNAL`. The whole call was rolled back and nothing was changed. Read the message:
- **Allocated:** the item is already out. Return it first.
- **Under Maintenance / Unavailable:** the item cannot be issued.
- **already Returned:** that allocation was closed earlier.

`ERROR 1305 (42000): PROCEDURE ... does not exist` means `11_transaction_procedures.sql` has not been run.

`Note (Code 1305)` messages printed while running `11` the first time are harmless. They come from `DROP PROCEDURE IF EXISTS` when the procedure did not exist yet.

## Errors with DELIMITER in GUI tools

`11_transaction_procedures.sql` uses `DELIMITER $$`, a command of the `mysql` command-line client.
- **MySQL Workbench:** open the file and run it with the "Execute (all)" lightning button. Workbench understands `DELIMITER`.
- **Other GUI tools:** these may not support `DELIMITER`. Run the file with the command-line client instead:
  ```bash
  mysql -u <user> -p < sql/11_transaction_procedures.sql
  ```

## Port conflicts

**Symptom:** the server will not start, and its error log says `Do you already have another mysqld server running on port: 3306 ?`

Another MySQL, MariaDB or XAMPP server is already using port 3306.
1. **Find the program using the port**

   | OS | Command |
   |---|---|
   | Linux | `sudo ss -ltnp \| grep 3306` |
   | macOS | `lsof -i :3306` |
   | Windows | `netstat -ano \| findstr 3306` |

2. **Fix it**, in one of two ways:
   - Stop the other server.
   - Or run MySQL on another port: set `port=3307` under `[mysqld]` in `my.cnf` / `my.ini`, then connect with `mysql -h 127.0.0.1 -P 3307 -u <user> -p`. Use `127.0.0.1`, not `localhost`: `localhost` makes the client use the socket and ignore the port.

## Version differences

| Feature used | Minimum version | What happens on older versions |
|---|---|---|
| CHECK constraints enforced | MySQL 8.0.16 | Constraints are ignored silently |
| Functional index (`uq_allocation_one_active_per_equipment`) | MySQL 8.0.13 | `02` fails with a syntax error |
| `REGEXP_LIKE()` in CHECK | MySQL 8.0.4 | `02` fails |
| `utf8mb4_0900_ai_ci` collation | MySQL 8.0 | `01` fails with "Unknown collation". Use MySQL 8 rather than editing the scripts. |

**MariaDB** is not MySQL. It accepts most of this SQL but differs in functional indexes and CHECK behaviour, so the project is only verified on MySQL 8.0 (tested on 8.0.46).

## `ONLY_FULL_GROUP_BY` errors in your own queries

**Symptom:** `ERROR 1055 (42000): Expression #2 of SELECT list is not in GROUP BY clause ...`

MySQL 8 requires every non-aggregated column in the SELECT list to appear in GROUP BY. Add the column to GROUP BY, as in `GROUP BY l.lab_id, l.lab_name`. All queries in this project already follow this rule. Do not disable the mode to hide the error.

## Different query results from the documentation

- **Overdue counts.** These depend on the date. The scripts use `@ref_date = 2026-10-10`. If you replaced it with `CURDATE()`, different allocations may be overdue.
- **Procedure tests.** If you ran the stored-procedure tests by hand on the development database, the data has changed. Reset and rebuild to return to the documented sample state.

---

## Web application (Review 3)

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'flask'` (or `mysql`) | Libraries not installed in the active Python | Activate the virtual environment (`source .venv/bin/activate`, or `.venv\Scripts\activate` on Windows), then `pip install -r requirements.txt` |
| Page shows "Error 500 … Check that the MySQL server is running" | The app cannot connect or log in | Start MySQL; check `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` in `.env`; test the same login with the `mysql` client |
| `Access denied for user 'root'@'localhost'` in the terminal | On Ubuntu, `root` often uses socket login and has no password | Create the `labadmin` account (README section 5), or set `DB_UNIX_SOCKET=/var/run/mysqld/mysqld.sock` with `DB_USER=root` |
| `OSError: [Errno 98] Address already in use` | Another program uses port 5000 (on macOS, often AirPlay Receiver) | Add `PORT=5001` to `.env` and open http://127.0.0.1:5001 |
| "Error 400: The form has expired" | The session cookie changed: the app restarted without a fixed `SECRET_KEY`, or the page was open for a long time | Reload the page and submit again; set a fixed `SECRET_KEY` in `.env` |
| `PROCEDURE smart_lab_equipment_db.sp_start_maintenance does not exist` | Script 12 not run | `mysql -u <user> -p < sql/12_maintenance_procedures.sql` |
| Dashboard shows 0 or a different number of overdue loans | `APP_REFERENCE_DATE` is not set, so the real date is used | Add `APP_REFERENCE_DATE=2026-10-10` to `.env` for the demo |
| Data differs from the screenshots | Earlier demo runs changed the data | Reset and rebuild (README section 9 and section 5) |
| `python -m pytest` fails while building the database | The account cannot create `smart_lab_equipment_apptest`, or the `mysql` client is not on PATH | Grant the privilege (tests/README.md); install the MySQL client or set `MYSQL_CLI` to its full path |
