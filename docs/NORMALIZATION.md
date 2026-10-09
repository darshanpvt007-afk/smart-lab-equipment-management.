# Normalization of the Schema

This document explains why the 10 tables in `sql/02_create_tables.sql` are in Third Normal Form (3NF). It works from the schema's own functional dependencies (FDs). The FDs are stated as **assumptions about the business**: they hold because of how the labs work, not because of the sample data.

## 1. Starting point: the manual register

Review 1 says the existing system keeps "registers or spreadsheets". A typical issue register looks like this single flat table:

| Reg. No | Student | Dept | Year | Equipment | Serial | Category | Lab | Lab Location | Issued By | Staff Phone | Issue Date | Due | Returned | Condition | Supplier | Invoice |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 24BCE1012 | Aarav Menon | CSE | 3 | DSO 100 MHz | OSC-DS1-0002 | Oscilloscope | Electronics and Circuits Lab | Block B, Room 204 | Priya Sundaram | 9000000202 | 2026-07-06 | 2026-07-13 | 2026-07-12 | Good | Apex Scientific | ASI-2025-0141 |
| 24BCE1012 | Aarav Menon | CSE | 3 | L2 Switch | NET-SW24-0012 | Networking Device | Computer Networks Lab | Block A, Room 101 | Ramesh Kumar | 9000000201 | 2026-07-22 | 2026-07-29 | 2026-07-30 | Good | Zenith Network | ZNS-2026-0023 |

This table suffers from all three classic anomalies:

| Anomaly | Example from this project |
|---|---|
| **Update** | Aarav's department, the lab's location or Priya's phone number is repeated in every row that mentions them. Changing one copy and missing another leaves contradictory data. |
| **Insertion** | A newly purchased spectrometer cannot be recorded until someone borrows it, because there is no row without a student. A new supplier cannot be recorded until an item is issued. |
| **Deletion** | Deleting the only allocation of the Laser Diffraction Kit would also erase which supplier and invoice it came from. |

Decomposing this register into the 10 entities of the ER diagram removes these anomalies, as shown below.

## 2. First Normal Form (1NF)

A table is in 1NF when:
- every column holds a single, atomic value
- there are no repeating groups
- each row is identified by a primary key

How the schema meets this:
- **Every table has a primary key** (`lab_id`, `equipment_id`, …).
- **No repeating groups.** A purchase that brings in 4 items does not have columns `item1, item2, item3, item4`, or a comma-separated list of serial numbers. Instead, each item is its own `equipment` row pointing to `purchase_id`. The same goes for allocations and maintenance: each event is a separate row, not a growing list inside `equipment`.
- **Atomic values.** For example:
  - `student_name` and `register_number` are separate columns.
  - The status and condition columns hold exactly one value from a fixed list, enforced by CHECK.
  - Dates are `DATE` values, not free text.
- **Location:** `location` ("Block B, Room 204") is treated as one atomic descriptive value, because the system never searches by block or room separately. If Review 3 needs that, it can be split into two columns.

## 3. Functional dependencies

`X → Y` means "a value of X determines exactly one value of Y".

| Table | Functional dependencies (assumed business rules) | Candidate keys |
|---|---|---|
| lab | lab_id → lab_name, location, capacity, lab_type; lab_name → lab_id | {lab_id}, {lab_name} |
| equipment_category | category_id → category_name, description; category_name → category_id | {category_id}, {category_name} |
| supplier | supplier_id → supplier_name, contact_number, email, address; supplier_name → supplier_id | {supplier_id}, {supplier_name} |
| student | student_id → student_name, register_number, department, year_of_study, email; register_number → student_id; email → student_id | {student_id}, {register_number}, {email} |
| lab_staff | staff_id → staff_name, designation, department, contact_number, email; email → staff_id | {staff_id}, {email} |
| purchase | purchase_id → supplier_id, purchase_date, invoice_number, total_amount, purchase_status; (supplier_id, invoice_number) → purchase_id | {purchase_id}, {supplier_id, invoice_number} |
| equipment | equipment_id → equipment_name, serial_number, equipment_condition, availability_status, category_id, lab_id, purchase_id; serial_number → equipment_id | {equipment_id}, {serial_number} |
| equipment_allocation | allocation_id → equipment_id, student_id, staff_id, allocation_date, expected_return_date, allocation_status | {allocation_id} |
| equipment_return | return_id → allocation_id, return_date, return_condition, remarks; allocation_id → return_id | {return_id}, {allocation_id} |
| maintenance | maintenance_id → equipment_id, staff_id, maintenance_date, maintenance_type, maintenance_cost, maintenance_status, remarks | {maintenance_id} |

**Dependencies deliberately *not* assumed** (they would be false in practice):

| Not assumed | Why |
|---|---|
| `equipment_name → category_id` | Names are free text, and the same name could be classified differently. |
| `department → anything` | No department-level facts (such as head of department) are stored. |
| `register_number → year_of_study` | The register number encodes the admission year, not the current year of study. Lateral entry or a repeated year breaks any formula. |
| `(equipment_id, allocation_date) → allocation_id` | A short loan could be returned and re-issued on the same day. |
| `capacity`, `location` and `lab_type` determining each other | None of these columns determines another. |

## 4. Second Normal Form (2NF)

A table is in 2NF when it is in 1NF and no non-key column depends on **only part** of a composite key.

- **Single-column primary keys.** All 10 primary keys have one column, so a partial dependency on the primary key is impossible.
- **The composite candidate key** is `(supplier_id, invoice_number)` in `purchase`. No non-key column depends on `supplier_id` alone:
  - The supplier's name, phone and address are **not** in `purchase`; they live in `supplier`.
  - `purchase_date`, `total_amount` and `purchase_status` need the whole invoice to be identified.
- The remaining multi-column keys are single-column alternatives (`serial_number`, `register_number`, …), so they cannot have partial dependencies.

All tables are therefore in 2NF.

## 5. Third Normal Form (3NF)

A table is in 3NF when it is in 2NF and no non-key column depends on another non-key column (no **transitive** dependency `key → A → B`).

Every determinant in the FD table above is a candidate key of its own table. That is the stronger **Boyce–Codd Normal Form (BCNF)** condition, so the tables are also in BCNF under the stated assumptions.

The important transitive dependencies that were *removed* by the decomposition:

| Transitive chain in the flat register | Where it was broken |
|---|---|
| allocation → equipment → **category name** | `equipment` stores only `category_id`. The name lives once in `equipment_category`. |
| allocation → equipment → lab → **lab location** | `equipment` stores only `lab_id`. The location lives once in `lab`. |
| equipment → purchase → **supplier** | `equipment` stores only `purchase_id`. `purchase` stores `supplier_id`. Supplier details live once in `supplier`. No `supplier_id` column was put in `equipment`, because that would be a transitive dependency. |
| allocation → student → **student name, department, year** | `equipment_allocation` stores only `student_id`. |
| allocation → staff → **staff phone, designation** | `equipment_allocation` and `maintenance` store only `staff_id`. |
| allocation → **return date, return condition** | These are facts about the return, so they live in `equipment_return`, keyed by `allocation_id`. This also avoids NULL-filled columns for unreturned allocations. |

## 6. Why each entity has its own table

| Separate table | Reason |
|---|---|
| supplier / purchase | One supplier, many purchases. Supplier contact details are stored once, and a supplier can exist before any purchase (no insertion anomaly). |
| purchase / equipment | One invoice, many items. Invoice facts (date, total, status) are stored once, not repeated for each item. |
| equipment_category / equipment | A category description is stored once. A category can exist before any item in it. |
| lab / equipment | Lab name, location and capacity are stored once. A lab can exist with no equipment. |
| student / equipment_allocation | Student details are stored once. A student who has never borrowed (Nisha Fernandes, student 10) is still recorded. |
| lab_staff / allocation & maintenance | One staff record serves both relationships (ISSUES and PERFORMS). |
| equipment_allocation / equipment | Allocation is a 1:N event over time. Storing "current borrower" columns in `equipment` would lose the history Review 1 requires. |
| equipment_return / equipment_allocation | Return facts exist only for returned allocations (1:1 optional). A separate table avoids NULL return columns and matches the ER diagram. |
| maintenance / equipment | Many services per item over its life. |

Results of the decomposition:
- **Update anomaly removed.** Changing a lab's location is one `UPDATE lab … WHERE lab_id = 2`, and every equipment row immediately "sees" the new value through the join.
- **Insertion anomaly removed.** Lab 4, supplier 3, category 6, student 10 and purchase 7 each exist on their own.
- **Deletion anomaly removed.** History rows are separate, and `ON DELETE RESTRICT` prevents deleting a parent while history refers to it.

## 7. Intentional redundancy and how it is controlled

Some stored values could, in principle, be computed from other tables. They are kept because they are **attributes in the approved ER diagram** and are needed for fast, simple reporting. This is not a normalization violation in the FD sense: each value depends only on its own table's key. It is, however, information that can be derived from another table, so it must be kept consistent.

| Stored value | Could be derived from | Why it is stored | How consistency is kept |
|---|---|---|---|
| `equipment.availability_status` | Existence of an `Issued` allocation, `In Progress` maintenance, condition | ER attribute Availability_Status; "real-time availability" objective; very common filter | Changed only together with allocations/returns inside `sp_allocate_equipment` / `sp_return_equipment`; CHECK forbids Damaged + Available; audited by V10, V11, V12 |
| `equipment_allocation.allocation_status` | Existence of an `equipment_return` row | ER attribute Allocation_Status; needed by the "one active allocation" unique index | Set to `Returned` in the same transaction that inserts the return; audited by V06, V07 |
| `equipment.equipment_condition` | Latest `return_condition` | ER attribute Condition; also set by purchases (New) and repairs, not only by returns | Updated by `sp_return_equipment`; audited by V12 |

No other derived values are stored:
- the number of items per lab
- total maintenance cost
- days overdue
- supplier totals

These are always computed with `COUNT`, `SUM` or `DATEDIFF` in queries and views, so they can never go out of date.

## 8. Department (a known limitation)

`department` appears as text in both `student` and `lab_staff` (e.g. `CSE`). It is an attribute in Review 1, and there is no Department entity, so it stays a column.
- It creates no transitive dependency, because nothing else about a department is stored.
- An inconsistent spelling such as `C.S.E.` or `Computer Science` would still be possible. Case alone is not a problem: the `utf8mb4_0900_ai_ci` collation is case-insensitive, so `cse` and `CSE` compare as equal. A separate `department` lookup table would prevent that, but it would add an entity the approved ER design does not have.
- This is a candidate improvement for Review 3, if the faculty agree.
