# Relational Schema

This schema converts the Review 1 ER diagram into 10 MySQL tables. The executable definition is in `sql/02_create_tables.sql`; this document describes the same schema in tabular form. All tables use the InnoDB engine and the `utf8mb4` character set, in the database `smart_lab_equipment_db`.

The ER diagram in Chen notation (entities, attributes, relationships, cardinality and participation) is in `docs/diagrams/ER_Chen.png` (also `.pdf` and `.svg`).

**Notation:** **PK** = primary key, **FK** = foreign key, **UQ** = unique, **NN** = NOT NULL, **AI** = AUTO_INCREMENT.

## Schema at a glance

```
lab                 (lab_id PK, lab_name UQ, location, capacity, lab_type)
equipment_category  (category_id PK, category_name UQ, description)
supplier            (supplier_id PK, supplier_name UQ, contact_number, email, address)
student             (student_id PK, student_name, register_number UQ, department, year_of_study, email UQ)
lab_staff           (staff_id PK, staff_name, designation, department, contact_number, email UQ)
purchase            (purchase_id PK, supplier_id FK, purchase_date, invoice_number, total_amount, purchase_status)
                     UQ (supplier_id, invoice_number)
equipment           (equipment_id PK, equipment_name, serial_number UQ, equipment_condition,
                     availability_status, category_id FK, lab_id FK, purchase_id FK)
equipment_allocation(allocation_id PK, equipment_id FK, student_id FK, staff_id FK,
                     allocation_date, expected_return_date, allocation_status)
equipment_return    (return_id PK, allocation_id FK UQ, return_date, return_condition, remarks)
maintenance         (maintenance_id PK, equipment_id FK, staff_id FK, maintenance_date,
                     maintenance_type, maintenance_cost, maintenance_status, remarks)
```

## Relationship diagram (foreign keys)

```
supplier 1 ──< purchase 1 ──< equipment >── 1 equipment_category
                                  │  \
                                  │   >── 1 lab
                                  │
               ┌──────────────────┼───────────────────┐
               ^                  ^                   ^
   equipment_allocation >── student          maintenance >── lab_staff
     │      \
     │       >── lab_staff (issued by)
     1
     │
     1 (optional)
 equipment_return

 Legend:  A 1 ──< B   one A has many B (FK in B)
          B >── 1 A   many B belong to one A (FK in B)
```

## Mapping of ER entities to tables

| Review 1 entity | Table | Review 1 primary key | Column |
|---|---|---|---|
| Lab | `lab` | Lab_ID | `lab_id` |
| Equipment Category | `equipment_category` | Category_ID | `category_id` |
| Supplier | `supplier` | Supplier_ID | `supplier_id` |
| Purchase | `purchase` | Purchase_ID | `purchase_id` |
| Student | `student` | Student_ID | `student_id` |
| Lab Staff | `lab_staff` | Staff_ID | `staff_id` |
| Equipment | `equipment` | Equipment_ID | `equipment_id` |
| Equipment Allocation | `equipment_allocation` | Allocation_ID | `allocation_id` |
| Equipment Return | `equipment_return` | Return_ID | `return_id` |
| Maintenance | `maintenance` | Maintenance_ID | `maintenance_id` |

Tables are created in dependency order: `lab`, `equipment_category`, `supplier`, `student`, `lab_staff`, `purchase`, `equipment`, `equipment_allocation`, `equipment_return`, `maintenance`.

---

## 1. `lab`

**Purpose:** the laboratories of the institution (Review 1 §6.5).

| Column | Type | Null | Key / Default | Notes |
|---|---|---|---|---|
| lab_id | INT | NN | PK, AI | Lab_ID |
| lab_name | VARCHAR(100) | NN | UQ `uq_lab_name` | Lab_Name |
| location | VARCHAR(150) | NN | | Location |
| capacity | SMALLINT | NN | CHECK `chk_lab_capacity`: `capacity > 0` | Capacity |
| lab_type | VARCHAR(50) | NN | | Lab_Type (Computer, Electronics, Physics …) |

Foreign keys: none. Referenced by `equipment.lab_id`.

## 2. `equipment_category`

**Purpose:** classification of equipment (Review 1 §6.4).

| Column | Type | Null | Key / Default | Notes |
|---|---|---|---|---|
| category_id | INT | NN | PK, AI | Category_ID |
| category_name | VARCHAR(80) | NN | UQ `uq_category_name` | Category_Name |
| description | VARCHAR(255) | NULL | | Description |

Foreign keys: none. Referenced by `equipment.category_id`.

## 3. `supplier`

**Purpose:** vendors that supply equipment (Review 1 §6.1).

| Column | Type | Null | Key / Default | Notes |
|---|---|---|---|---|
| supplier_id | INT | NN | PK, AI | Supplier_ID |
| supplier_name | VARCHAR(120) | NN | UQ `uq_supplier_name` | Supplier_Name |
| contact_number | VARCHAR(15) | NN | CHECK `chk_supplier_contact`: 10–14 digits, optional leading `+` | Contact_Number |
| email | VARCHAR(120) | NULL | CHECK `chk_supplier_email`: `name@domain.tld` shape | Email |
| address | VARCHAR(255) | NULL | | Address |

Foreign keys: none. Referenced by `purchase.supplier_id`.

## 4. `student`

**Purpose:** students who receive equipment (Review 1 §6.8).

| Column | Type | Null | Key / Default | Notes |
|---|---|---|---|---|
| student_id | INT | NN | PK, AI | Student_ID |
| student_name | VARCHAR(100) | NN | | Student_Name |
| register_number | VARCHAR(15) | NN | UQ `uq_student_register_no`; CHECK `chk_student_register_no`: format `24BCE1012` (2 digits, 3 capitals, 4 digits; case-sensitive) | Register_Number |
| department | VARCHAR(60) | NN | INDEX `idx_student_department_year` | Department |
| year_of_study | TINYINT | NN | CHECK `chk_student_year`: 1–5 | Year (renamed, see D-02) |
| email | VARCHAR(120) | NN | UQ `uq_student_email`; CHECK `chk_student_email` | Email |

Foreign keys: none. Referenced by `equipment_allocation.student_id`.

## 5. `lab_staff`

**Purpose:** laboratory staff who issue equipment and perform maintenance (Review 1 §6.10).

| Column | Type | Null | Key / Default | Notes |
|---|---|---|---|---|
| staff_id | INT | NN | PK, AI | Staff_ID |
| staff_name | VARCHAR(100) | NN | | Staff_Name |
| designation | VARCHAR(60) | NN | | Designation |
| department | VARCHAR(60) | NN | | Department |
| contact_number | VARCHAR(15) | NN | CHECK `chk_lab_staff_contact` | Contact_Number |
| email | VARCHAR(120) | NN | UQ `uq_lab_staff_email`; CHECK `chk_lab_staff_email` | Email |

Foreign keys: none. Referenced by `equipment_allocation.staff_id` and `maintenance.staff_id`.

## 6. `purchase`

**Purpose:** procurement records (Review 1 §6.2).

| Column | Type | Null | Key / Default | Notes |
|---|---|---|---|---|
| purchase_id | INT | NN | PK, AI | Purchase_ID |
| supplier_id | INT | NN | **FK** `fk_purchase_supplier` | Implements SUPPLIES |
| purchase_date | DATE | NN | INDEX `idx_purchase_date` | Purchase_Date |
| invoice_number | VARCHAR(30) | NN | UQ `(supplier_id, invoice_number)` | Invoice_Number (see D-06) |
| total_amount | DECIMAL(12,2) | NN | CHECK `chk_purchase_amount`: `> 0` | Total_Amount, INR |
| purchase_status | VARCHAR(20) | NN | DEFAULT `'Ordered'`; CHECK: Ordered / Received / Cancelled | Purchase_Status |

| Foreign key | References | Relationship | ON DELETE / ON UPDATE |
|---|---|---|---|
| supplier_id | `supplier(supplier_id)` | Supplier 1:N Purchase (SUPPLIES) | RESTRICT / CASCADE |

## 7. `equipment` (central entity)

**Purpose:** each physical equipment item (Review 1 §6.3).

| Column | Type | Null | Key / Default | Notes |
|---|---|---|---|---|
| equipment_id | INT | NN | PK, AI | Equipment_ID |
| equipment_name | VARCHAR(120) | NN | INDEX `idx_equipment_name` | Equipment_Name |
| serial_number | VARCHAR(50) | NN | UQ `uq_equipment_serial_number` | Serial_Number |
| equipment_condition | VARCHAR(20) | NN | DEFAULT `'New'`; CHECK: New / Good / Fair / Damaged | Condition (renamed, see D-02) |
| availability_status | VARCHAR(20) | NN | DEFAULT `'Available'`; CHECK: Available / Allocated / Under Maintenance / Unavailable; INDEX | Availability_Status |
| category_id | INT | NN | **FK** `fk_equipment_category` | Implements CLASSIFIES |
| lab_id | INT | NN | **FK** `fk_equipment_lab` | Implements CONTAINS |
| purchase_id | INT | NN | **FK** `fk_equipment_purchase` | Implements RESULTS_IN |

Table-level CHECK `chk_equipment_damaged_not_available`: `NOT (equipment_condition = 'Damaged' AND availability_status = 'Available')`.

| Foreign key | References | Relationship | ON DELETE / ON UPDATE |
|---|---|---|---|
| category_id | `equipment_category(category_id)` | Category 1:N Equipment (CLASSIFIES) | RESTRICT / CASCADE |
| lab_id | `lab(lab_id)` | Lab 1:N Equipment (CONTAINS) | RESTRICT / CASCADE |
| purchase_id | `purchase(purchase_id)` | Purchase 1:N Equipment (RESULTS_IN) | RESTRICT / CASCADE |

## 8. `equipment_allocation`

**Purpose:** issue of an equipment item to a student by a staff member (Review 1 §6.6).

| Column | Type | Null | Key / Default | Notes |
|---|---|---|---|---|
| allocation_id | INT | NN | PK, AI | Allocation_ID |
| equipment_id | INT | NN | **FK** `fk_allocation_equipment` | Implements IS_ALLOCATED |
| student_id | INT | NN | **FK** `fk_allocation_student` | Implements RECEIVES |
| staff_id | INT | NN | **FK** `fk_allocation_staff` | Implements ISSUES |
| allocation_date | DATE | NN | INDEX `idx_allocation_date` | Allocation_Date |
| expected_return_date | DATE | NN | CHECK `chk_allocation_dates`: `>= allocation_date` | Expected_Return_Date |
| allocation_status | VARCHAR(20) | NN | DEFAULT `'Issued'`; CHECK: Issued / Returned | Allocation_Status |

Additional indexes:
- `uq_allocation_one_active_per_equipment`: a **functional UNIQUE** index on `(CASE WHEN allocation_status = 'Issued' THEN equipment_id END)`. It allows at most one active allocation per equipment item (D-10).
- `idx_allocation_status_due (allocation_status, expected_return_date)`: supports the outstanding and overdue queries.

| Foreign key | References | Relationship | ON DELETE / ON UPDATE |
|---|---|---|---|
| equipment_id | `equipment(equipment_id)` | Equipment 1:N Allocation (IS_ALLOCATED) | RESTRICT / CASCADE |
| student_id | `student(student_id)` | Student 1:N Allocation (RECEIVES) | RESTRICT / CASCADE |
| staff_id | `lab_staff(staff_id)` | Lab Staff 1:N Allocation (ISSUES) | RESTRICT / CASCADE |

## 9. `equipment_return`

**Purpose:** return of an allocated item (Review 1 §6.9).

| Column | Type | Null | Key / Default | Notes |
|---|---|---|---|---|
| return_id | INT | NN | PK, AI | Return_ID |
| allocation_id | INT | NN | **FK** `fk_return_allocation`; **UQ** `uq_return_allocation` | Implements HAS_RETURN (1:1) |
| return_date | DATE | NN | | Return_Date |
| return_condition | VARCHAR(20) | NN | CHECK: Good / Fair / Damaged | Return_Condition |
| remarks | VARCHAR(255) | NULL | | Remarks |

| Foreign key | References | Relationship | ON DELETE / ON UPDATE |
|---|---|---|---|
| allocation_id | `equipment_allocation(allocation_id)` | Allocation 1:1 Return (HAS_RETURN) | RESTRICT / CASCADE |

**The 1:1 relationship:**
- `NOT NULL` + FK: every return belongs to exactly one allocation.
- `UNIQUE`: an allocation has at most one return.
- An allocation that has not been returned has no row here (optional participation). See D-04.

## 10. `maintenance`

**Purpose:** servicing, repair and calibration activities (Review 1 §6.7).

| Column | Type | Null | Key / Default | Notes |
|---|---|---|---|---|
| maintenance_id | INT | NN | PK, AI | Maintenance_ID |
| equipment_id | INT | NN | **FK** `fk_maintenance_equipment` | Implements UNDERGOES |
| staff_id | INT | NN | **FK** `fk_maintenance_staff` | Implements PERFORMS |
| maintenance_date | DATE | NN | | Maintenance_Date |
| maintenance_type | VARCHAR(20) | NN | CHECK: Preventive / Repair / Calibration | Maintenance_Type |
| maintenance_cost | DECIMAL(10,2) | NULL | CHECK `chk_maintenance_cost`: `>= 0` | Maintenance_Cost; NULL until known (D-12) |
| maintenance_status | VARCHAR(20) | NN | DEFAULT `'Scheduled'`; CHECK: Scheduled / In Progress / Completed; INDEX | Maintenance_Status |
| remarks | VARCHAR(255) | NULL | | Remarks |

Table-level CHECK `chk_maintenance_completed_cost`: `maintenance_status <> 'Completed' OR maintenance_cost IS NOT NULL`.

| Foreign key | References | Relationship | ON DELETE / ON UPDATE |
|---|---|---|---|
| equipment_id | `equipment(equipment_id)` | Equipment 1:N Maintenance (UNDERGOES) | RESTRICT / CASCADE |
| staff_id | `lab_staff(staff_id)` | Lab Staff 1:N Maintenance (PERFORMS) | RESTRICT / CASCADE |

---

## Indexes

InnoDB automatically indexes every foreign key column, which speeds up the joins. The extra indexes below support common searches.

| Index | Table | Used by |
|---|---|---|
| `idx_student_department_year` | student | Q07, Q08 (filter by department / year) |
| `idx_purchase_date` | purchase | Q13 (sort purchases by date) |
| `idx_equipment_availability` | equipment | Q06, Q26 (filter by availability) |
| `idx_equipment_name` | equipment | Q04, Q12 (name search / sort) |
| `idx_allocation_status_due` | equipment_allocation | Q10, Q11, V15 (outstanding / overdue) |
| `idx_allocation_date` | equipment_allocation | Q09, Q14 (date range / latest) |
| `idx_maintenance_status` | maintenance | Q21, V11, V16 |
| `uq_allocation_one_active_per_equipment` | equipment_allocation | Business rule D-10 |

## Views (sql/08_create_views.sql)

| View | Base tables | One row per |
|---|---|---|
| `vw_equipment_inventory` | equipment, equipment_category, lab, purchase, supplier | equipment item |
| `vw_outstanding_allocations` | equipment_allocation (Issued only), student, equipment, lab, lab_staff | outstanding allocation |
| `vw_maintenance_history` | maintenance, equipment, lab, lab_staff | maintenance record |
| `vw_allocation_history` | equipment_allocation, student, equipment, lab_staff, LEFT JOIN equipment_return | allocation |

## Stored procedures (sql/11_transaction_procedures.sql, sql/12_maintenance_procedures.sql)

| Procedure | Tables changed atomically |
|---|---|
| `sp_allocate_equipment(equipment, student, staff, date, expected_return, OUT id)` | `equipment_allocation` (INSERT), `equipment` (UPDATE availability) |
| `sp_return_equipment(allocation, date, condition, remarks)` | `equipment_return` (INSERT), `equipment_allocation` (UPDATE status), `equipment` (UPDATE condition and availability) |
| `sp_start_maintenance(maintenance, start_date)` (file 12) | `maintenance` (UPDATE status and date), `equipment` (UPDATE availability) |
| `sp_complete_maintenance(maintenance, cost, condition_after, remarks)` (file 12) | `maintenance` (UPDATE status, cost, remarks), `equipment` (UPDATE condition and availability) |

## How to inspect the schema in MySQL

```sql
USE smart_lab_equipment_db;
SHOW TABLES;
DESCRIBE equipment;
SHOW CREATE TABLE equipment_allocation\G

-- All primary keys, unique keys, foreign keys and checks:
SELECT TABLE_NAME, CONSTRAINT_NAME, CONSTRAINT_TYPE
FROM information_schema.TABLE_CONSTRAINTS
WHERE TABLE_SCHEMA = 'smart_lab_equipment_db'
ORDER BY TABLE_NAME, CONSTRAINT_TYPE;

-- Every foreign key with its parent table:
SELECT TABLE_NAME, COLUMN_NAME, CONSTRAINT_NAME,
       REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = 'smart_lab_equipment_db'
  AND REFERENCED_TABLE_NAME IS NOT NULL
ORDER BY TABLE_NAME;

-- CHECK constraint definitions:
SELECT CONSTRAINT_NAME, CHECK_CLAUSE
FROM information_schema.CHECK_CONSTRAINTS
WHERE CONSTRAINT_SCHEMA = 'smart_lab_equipment_db';
```
