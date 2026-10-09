# Design Decisions — Review 2

This file records every decision made while converting the approved Review 1 ER design into the MySQL database, including each place where the implementation adds something the Review 1 document does not state explicitly. All ten entities and all ten relationships from Review 1 are implemented with their original cardinalities. **No entity was added or removed, and no cardinality was changed.**

Sources:
- *DOC-20261005-WA0014.pdf*: the Review 1 presentation (slides 1–11) and report (pages 12–26)
- *DATABASE SYSTEMS L3+L4.pdf*: the official review instructions

---

## D-01 Project layout

The repository root plays the role of the `smart-lab-equipment/` folder in the requested structure. The only file already in the repository was a two-line `README.md`; it was replaced by the full project README, and its title is kept.

Additions beyond the requested structure:

| File | Why |
|---|---|
| `sql/11_transaction_procedures.sql` | Atomic allocation and return procedures, kept in a separate file so the basic scripts stay simple (Phase 6). |
| `tests/run_tests.sh` | Runs all SQL tests automatically against a separate test database (63 in Review 2; 71 after Review 3 added the maintenance procedures; 74 with the register-number check). |

## D-02 Table and column naming

- All tables and columns use `snake_case`, and table names are singular, as requested (`lab`, `equipment_category`, …).
- Column names follow the Review 1 attribute names (`Supplier_Name` → `supplier_name`, `Expected_Return_Date` → `expected_return_date`, …).
- Two attributes are renamed because their Review 1 names are SQL keywords:

| Review 1 attribute | Column | Reason |
|---|---|---|
| Equipment.**Condition** | `equipment_condition` | `CONDITION` is a **reserved word** in MySQL 8. An unquoted `condition` column is a syntax error. |
| Student.**Year** | `year_of_study` | `YEAR` is a keyword, a data type and a function in MySQL. Renaming it avoids confusion and back-tick quoting. |

## D-03 Foreign keys added to implement the approved relationships

Review 1 lists only each entity's descriptive attributes. Relationships appear as diamonds in the ER diagram and in sections 7–8 of the report. A relational database implements a 1:N relationship by placing the parent's primary key, as a foreign key, in the table on the **N** side. These 10 columns are therefore **required** to implement relationships that are already approved. They are not new attributes.

| # | Relationship (Review 1) | Cardinality | Foreign key column | References |
|---|---|---|---|---|
| 1 | Supplier — SUPPLIES — Purchase | 1:N | `purchase.supplier_id` | `supplier.supplier_id` |
| 2 | Purchase — RESULTS_IN — Equipment | 1:N | `equipment.purchase_id` | `purchase.purchase_id` |
| 3 | Equipment Category — CLASSIFIES — Equipment | 1:N | `equipment.category_id` | `equipment_category.category_id` |
| 4 | Lab — CONTAINS — Equipment | 1:N | `equipment.lab_id` | `lab.lab_id` |
| 5 | Equipment — IS_ALLOCATED — Equipment Allocation | 1:N | `equipment_allocation.equipment_id` | `equipment.equipment_id` |
| 6 | Student — RECEIVES — Equipment Allocation | 1:N | `equipment_allocation.student_id` | `student.student_id` |
| 7 | Lab Staff — ISSUES — Equipment Allocation | 1:N | `equipment_allocation.staff_id` | `lab_staff.staff_id` |
| 8 | Equipment Allocation — HAS_RETURN — Equipment Return | 1:1 | `equipment_return.allocation_id` (UNIQUE) | `equipment_allocation.allocation_id` |
| 9 | Equipment — UNDERGOES — Maintenance | 1:N | `maintenance.equipment_id` | `equipment.equipment_id` |
| 10 | Lab Staff — PERFORMS — Maintenance | 1:N | `maintenance.staff_id` | `lab_staff.staff_id` |

All foreign key columns are `NOT NULL`. Review 1 says each child belongs to exactly one parent: each purchase "is associated with one supplier", each equipment item belongs to "one Lab, one Category and one Purchase", and each allocation is "for one equipment, one student, and issued by one staff member".

## D-04 The 1:1 Allocation–Return relationship

Review 1 says: "each allocation has at most one return" and "each return belongs to exactly one allocation."

**Implementation:** `equipment_return.allocation_id` is a foreign key that is both `NOT NULL` and `UNIQUE`.

| Requirement | How it is enforced |
|---|---|
| Every return belongs to one allocation | `NOT NULL` + FOREIGN KEY |
| An allocation has at most one return | `UNIQUE (allocation_id)` (test TC22) |
| An allocation may have no return yet | The key lives in the *return* table, so an unreturned allocation simply has no matching row (test TC25) |

Alternatives that were rejected:
- **A `return_id` column in `equipment_allocation`.** It would be NULL for every outstanding allocation, and recording a return would need an extra UPDATE.
- **Merging the two tables.** Review 1 models Equipment Return as a separate entity, so the tables stay separate.

## D-05 Primary keys and business identifiers

- Every table has an `INT AUTO_INCREMENT` surrogate primary key named after the Review 1 key (`Supplier_ID` → `supplier_id`, …). Surrogate keys are stable: they never change even if a name, e-mail or invoice number is corrected.
- Real-world identifiers are protected with `UNIQUE` constraints so duplicates are still impossible:

| Table | UNIQUE | Justification |
|---|---|---|
| `student` | `register_number`, `email` | A register number identifies one student. A student e-mail belongs to one student. |
| `equipment` | `serial_number` | A manufacturer serial number identifies one physical item. |
| `purchase` | `(supplier_id, invoice_number)` | See D-06. |
| `lab_staff` | `email` | An official e-mail belongs to one staff member. |
| `lab` | `lab_name` | Two labs with the same name would be ambiguous. |
| `equipment_category` | `category_name` | A category name must be unambiguous. |
| `supplier` | `supplier_name` | Prevents registering the same vendor twice. |

`supplier.email` is not unique, because one shared sales address could serve two branches registered separately.

## D-06 Invoice number uniqueness is per supplier

Invoice numbers are created by the supplier. Two different suppliers can legitimately both issue an invoice numbered `INV-0001`. Uniqueness is therefore `UNIQUE (supplier_id, invoice_number)` rather than `UNIQUE (invoice_number)`. Tests TC11 and TC12 cover both cases.

## D-07 Value domains (CHECK constraints)

Review 1 names the status and condition attributes but does not list their values. The value sets below were chosen to match the Review 1 text, which mentions available, allocated, maintenance, repair, calibration, preventive maintenance, servicing and condition. CHECK constraints are enforced from MySQL 8.0.16.

| Column | Allowed values |
|---|---|
| `equipment.equipment_condition` | New, Good, Fair, Damaged |
| `equipment.availability_status` | Available, Allocated, Under Maintenance, Unavailable |
| `equipment_allocation.allocation_status` | Issued, Returned |
| `equipment_return.return_condition` | Good, Fair, Damaged |
| `maintenance.maintenance_type` | Preventive, Repair, Calibration |
| `maintenance.maintenance_status` | Scheduled, In Progress, Completed |
| `purchase.purchase_status` | Ordered, Received, Cancelled |

Other CHECK constraints:
- `lab.capacity > 0`
- `student.year_of_study BETWEEN 1 AND 5`
- `student.register_number` matches `^[0-9]{2}[A-Z]{3}[0-9]{4}$` with `REGEXP_LIKE(…, 'c')` (`chk_student_register_no`). Added after Review 3 so the database enforces the same rule as the web form, even for SQL that bypasses the app. The `'c'` flag is required: the default collation `utf8mb4_0900_ai_ci` is case-insensitive, so without it `24bce1012` would pass. Tests TC72–TC74, TA48.
- `purchase.total_amount > 0`
- `maintenance.maintenance_cost >= 0`
- `expected_return_date >= allocation_date`
- phone numbers: 10–14 digits, with an optional leading `+`
- e-mail addresses: basic `name@domain.tld` shape

These columns use `VARCHAR` + `CHECK` rather than MySQL `ENUM` because `CHECK` is standard SQL and the allowed values are visible in the table definition.

## D-08 Availability: stored, single writer, audited

Review 1 lists **Availability_Status** as an attribute of Equipment, and its functional requirements say to "track condition and availability status". It is therefore a **stored column**. Its value could also be derived from the allocation and maintenance tables. Two sources of truth could disagree, so the design applies these rules:

1. **Meaning of each value**

| availability_status | Meaning | Must agree with |
|---|---|---|
| Available | Can be issued now | No `Issued` allocation, no `In Progress` maintenance, condition is not Damaged |
| Allocated | With a student | Exactly one `Issued` allocation |
| Under Maintenance | Being serviced | At least one `In Progress` maintenance record |
| Unavailable | Not usable and not being worked on (e.g. returned Damaged, repair only *scheduled*) | — |

2. **Single writer.** `availability_status` is changed together with the allocation or return, inside one transaction, by `sp_allocate_equipment` / `sp_return_equipment` (D-10, file 11). Review 3 must use these procedures, or the same transaction logic, rather than ad-hoc UPDATEs.
3. **Audit.** Validation queries V10 and V11 report any row where the stored status disagrees with the history. Test TC39 shows that V10 catches a deliberately corrupted status.
4. **Hard guarantee.** The CHECK constraint `chk_equipment_damaged_not_available` makes "Damaged and Available" impossible.

`allocation_status` and `equipment_condition` are handled the same way:
- `allocation_status` must be `Returned` exactly when a return row exists (V06, V07).
- `equipment_condition` holds the *current* condition. The return procedure copies the return condition into it.

## D-09 Reference date for date-based queries

The sample data describes the labs on **2026-10-10**, just before the Review 2 deadline of 12 October 2026. Queries that depend on "today" (overdue loans, invalid future dates) use the session variable `SET @ref_date = DATE '2026-10-10'` so the demonstration gives the same results on any day. Each such query notes that `CURDATE()` replaces `@ref_date` for live use.

On any day from 2026-10-09 to 2026-10-12 inclusive, `CURDATE()` also returns the same three overdue allocations (15, 16, 17).

"Overdue" is **never stored**. It is computed by comparing `expected_return_date` with the date, so it cannot become stale.

## D-10 One equipment item cannot be issued to two students at once

This is a rule *across rows*. A per-row CHECK constraint cannot express it, and a foreign key does not express it. It is enforced by three layers:

| Layer | Mechanism | What it guarantees |
|---|---|---|
| 1. Database constraint | Functional unique index `uq_allocation_one_active_per_equipment` on `(CASE WHEN allocation_status='Issued' THEN equipment_id END)` | The index holds `equipment_id` only for `Issued` rows; returned rows are NULL, and UNIQUE ignores NULLs. So any number of past allocations may exist, but **at most one active allocation per item**. Because it is a unique index, InnoDB enforces it under concurrency: a second concurrent insert waits for the first and then fails with error 1062 (tests TC23, TC54). |
| 2. Controlled transaction | `sp_allocate_equipment` locks the equipment row with `SELECT … FOR UPDATE`, checks that it is `Available`, inserts and updates, then COMMITs. | Concurrent requests for the same item are serialised. The second request re-reads the status, sees `Allocated`, and is refused with a clear message (test TC53). Items under maintenance or damaged are refused (TC44, TC45). |
| 3. Audit | Validation queries V08 (two active rows) and V09 (overlapping historical loan periods) | Detects problems in history, for example data imported from old registers (TC40). |

**Why not a trigger?**
- A `BEFORE INSERT` trigger that runs `SELECT COUNT(*) … WHERE allocation_status='Issued'` uses a non-locking read. Two concurrent transactions can both see zero active rows and both insert.
- Making a trigger safe needs explicit locking, which is harder to explain.
- The unique index gives the guarantee declaratively and is concurrency-safe by construction.

Functional indexes need MySQL 8.0.13 or later.

**Review 3 application.** The application should call `sp_allocate_equipment` / `sp_return_equipment`, or reproduce their steps inside one transaction with `SELECT … FOR UPDATE`. It should also:
- show the procedure's error message to the user
- treat error 1062 on this index as "item is already issued"
- validate dates and IDs before calling, for friendlier messages, while still relying on the database for the final guarantee

## D-11 Damaged equipment

Review 1 does not say whether damaged equipment may be issued. **Chosen rule:** damaged equipment may **not** be issued.

- **CHECK constraint.** A damaged item can never be `Available`.
- **Allocation procedure.** It refuses anything that is not `Available`, and refuses anything `Damaged`.
- **Return as Damaged.** `sp_return_equipment` sets the item's condition to Damaged and its availability to `Unavailable` (TC52).
- **Back into service.** A repair is recorded in `maintenance`. Only after it is completed may staff set the item back to a usable condition and `Available`. V12 flags any item that was returned damaged and put back into service without a later completed maintenance.

A maintenance-workflow procedure, setting `Under Maintenance` when a job starts and `Available` when it completes, is listed for Review 3. In the sample data and the audit, an `In Progress` job means `Under Maintenance`. A `Scheduled` future job does not by itself change availability: equipment 5 stays Available until its calibration starts.

## D-12 Maintenance cost may be NULL until known

A `Scheduled` job has no cost yet.
- Storing `0.00` would be false information, and it would pull down `AVG()`.
- `maintenance_cost` is therefore nullable, and `AVG` / `SUM` ignore NULL (Q20 shows the difference between `COUNT(*)` and `COUNT(maintenance_cost)`).
- The CHECK `chk_maintenance_completed_cost` requires a cost once a job is `Completed`.
- An `In Progress` job may already carry the agreed or quoted cost.

## D-13 History is never deleted by cascade

Every foreign key is `ON DELETE RESTRICT`. Deleting a student, an equipment item, an allocation with a return, or a supplier with purchases is refused while history refers to it (TC56–TC59). This preserves the purchase, allocation, return and maintenance history that Review 1 requires ("the design keeps a full history of purchase, usage, return and maintenance").

`ON UPDATE CASCADE` is used so that, in the rare case a surrogate key is changed, child rows follow it rather than being orphaned.

A "retire / deactivate" flag for removing items from active use without deleting them is **not** added, because Review 1 does not define one. It is listed for Review 3 if the faculty want it.

## D-14 Data types

| Data | Type | Reason |
|---|---|---|
| Money | `DECIMAL(12,2)` (purchase), `DECIMAL(10,2)` (maintenance) | Exact decimal arithmetic. FLOAT cannot store values such as 0.10 exactly. |
| Dates | `DATE` | Review 1 records dates (Allocation_Date, Return_Date, …), not times. |
| Names / addresses | `VARCHAR(100–255)` | Variable length. |
| Phone numbers | `VARCHAR(15)` | Not a number: it can start with `+` or `0`, and nobody does arithmetic on it. |
| Year of study, capacity | `TINYINT`, `SMALLINT` | Small whole numbers. |

## D-15 Department is a plain attribute, not an entity

Student and Lab Staff each have a `Department` attribute in Review 1, and there is no Department entity. It is stored as text (e.g. `CSE`) in both tables. Adding a `department` table would add an entity the approved design does not have. NORMALIZATION.md discusses the effect.

## D-16 Purchase total vs. equipment

Review 1 gives Purchase a `Total_Amount` but gives Equipment no price. The total is therefore an independent fact of the invoice: it may include taxes, shipping and accessories. It cannot be derived from other columns, so storing it is not redundancy.

## D-17 Discrepancies noticed in the Review 1 material (no design change)

| Location | Observation | Treatment |
|---|---|---|
| Slide "Database Keys & Relationships" | Mentions "UserID for Users table" and "Users manage equipment". There is no *Users* entity among the 10 entities. | The detailed report (sections 6–8) and the ER diagram use Student and Lab Staff, so they are authoritative. No `users` table was created. Login accounts belong to Review 3, if needed. |
| Slide "Relationships & Cardinality" | "Supplier 1 : N Purchase" appears twice. | Duplicate bullet. One relationship is implemented. |
| Slides "Proposed System" / "Conclusion" | Promise "automated maintenance alerts". | A database cannot push alerts by itself. Review 2 provides the *queries* an alert would use: Q11/Q53 overdue loans, V15/V16 overdue maintenance. Scheduling and notification belong to the Review 3 application. |

## D-18 Sample data

- All names, register numbers, phone numbers and e-mails are fictional. E-mail addresses use the reserved `example.com` / `example.edu` domains.
- Phone numbers use the placeholder pattern `90000001xx` / `90000002xx`.
- Primary key values are written explicitly in the INSERTs so the foreign key values are readable.
- The data is loaded in one transaction.
- The sample state agrees with every rule above. `09_validation_queries.sql` finds no violations, and tests TC38 and TC63 prove it.

## D-19 Calling the procedures

`START TRANSACTION` inside a stored procedure implicitly commits any transaction the caller already had open. The procedures must therefore be called on their own, not inside an outer transaction. The header of file 11 documents this.

---

## Review 3 decisions

## D-20 Maintenance workflow procedures

`sql/12_maintenance_procedures.sql` adds `sp_start_maintenance` and `sp_complete_maintenance`. This completes the rule in D-08 that `Under Maintenance` ⇔ an `In Progress` job, which until now held only in the sample data.

| Procedure | Behaviour |
|---|---|
| `sp_start_maintenance` | Refuses a job that is not `Scheduled`. Refuses work on an item that is currently `Allocated` (it is with a student). Otherwise sets the job `In Progress` with the start date and the item `Under Maintenance`. |
| `sp_complete_maintenance` | Requires a cost of 0 or more, then records it. Sets the item's new condition. The item becomes `Available`, or `Unavailable` if still Damaged, unless another job on it is still in progress. |

Scheduling a job is a plain INSERT with status `Scheduled`, and it does not change availability. Both procedures follow file 11's conventions: lock the equipment row first, one transaction, ROLLBACK + RESIGNAL, error 1644 for refusals. Tests TC64–TC71 and TA25–TA27 cover them.

## D-21 The web application changes statuses only through workflows

The CRUD forms never edit `availability_status`, `equipment_condition`, `allocation_status` or `maintenance_status`:
- **New equipment** starts `Available`, with condition New, Good or Fair.
- **Later changes** happen only through Issue, Return, Start and Complete, each a stored procedure.
- **Plain forms** exist only for allocation and maintenance *creation*: the Issue form calls the procedure, and the Schedule form inserts a `Scheduled` job.

Two more rules are enforced in the app:
- **Purchase status.** A purchase that already has equipment must stay `Received` (audit V14).
- **Register number format.** The pattern `24BCE1012` (2 digits, 3 letters, 4 digits) is checked by the form, not by the database, because Review 1 did not fix a format.

## D-22 Application security and configuration

| Concern | Measure |
|---|---|
| SQL injection | User input reaches MySQL only as a `%s` parameter. Search WHERE clauses are built from fixed strings (TA06). |
| Cross-site request forgery | A random per-session token must accompany every POST, and a POST without it is rejected with 400 (TA30). |
| Cross-site scripting | Jinja escapes every value (TA31). |
| Credentials | Credentials come from environment variables or the git-ignored `.env`; nothing is hard-coded. `SECRET_KEY` falls back to a random value per start. |
| Authentication | Not implemented. The course does not require it, and it is listed as a next step. |

## D-23 Enterprise user interface without new tables or dependencies

The interface was redesigned after Review 3's first prototype (mockup first, then built). The redesign changes no table, view or procedure.

| Choice | Reason |
|---|---|
| Activity timeline built from existing tables with `UNION ALL` (`app/activity.py`) | Purchase, allocation, return and maintenance rows already record every event, so an audit table would duplicate data (3NF, Review 2). Planned maintenance is left out of "last activity" because it has not happened yet. |
| Sorting through a whitelist of ORDER BY expressions | A column name cannot be sent as a `%s` parameter, so `?sort=` selects one of fixed strings; anything else falls back to the default (TA41). |
| Saved views and paging are URL parameters | Bookmarkable, work without JavaScript, testable with plain GET requests (TA40, TA42). |
| CSV cells starting with `= + - @` are prefixed with `'` | Prevents spreadsheet formula injection when the export is opened in Excel (TA44). |
| Badges keep the database terms (Allocated, Under Maintenance) | The screens match the schema and the SQL shown on the Reports page. |
| No web fonts, CSS framework or JavaScript framework | Works offline in the lab; IBM Plex is used if installed, otherwise the system font. `app.js` only adds conveniences; every page works without it. |
| Signed-in user shown as "Lab desk · No sign-in (prototype)" | The mockup showed a named user, but there is no login yet (D-22); the screen must not suggest otherwise. |
