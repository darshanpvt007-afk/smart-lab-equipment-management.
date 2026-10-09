-- =====================================================================
-- File   : 02_create_tables.sql
-- Purpose: Convert the Review 1 ER diagram into 10 relational tables
--          with primary keys, foreign keys and integrity constraints.
-- Target : MySQL 8.0.16+ (CHECK constraints are enforced from 8.0.16;
--          functional indexes need 8.0.13+). Tested on MySQL 8.0.46.
--
-- Run after 01_create_database.sql:
--     mysql -u <user> -p < sql/02_create_tables.sql
--
-- This script does NOT drop anything. On a database that already has
-- these tables it stops with "Table ... already exists"; use
-- 10_reset_database.sql (destructive, deliberate) to start over.
--
-- Creation order (parents before children):
--   lab, equipment_category, supplier, student, lab_staff   (no FKs)
--   purchase            -> supplier
--   equipment           -> equipment_category, lab, purchase
--   equipment_allocation-> equipment, student, lab_staff
--   equipment_return    -> equipment_allocation   (1:1)
--   maintenance         -> equipment, lab_staff
--
-- Naming: snake_case. The ER attribute "Condition" is stored as
-- equipment_condition (CONDITION is a reserved word in MySQL) and
-- "Year" as year_of_study. See docs/DESIGN_DECISIONS.md.
--
-- Referential actions: ON DELETE RESTRICT everywhere so that deleting a
-- parent can never silently erase purchase, allocation, return or
-- maintenance history. ON UPDATE CASCADE keeps children correct if a
-- surrogate key value is ever changed.
-- =====================================================================

USE smart_lab_equipment_db;

-- ---------------------------------------------------------------------
-- 1. lab  (ER entity: Lab)
-- ---------------------------------------------------------------------
CREATE TABLE lab (
    lab_id     INT          NOT NULL AUTO_INCREMENT,
    lab_name   VARCHAR(100) NOT NULL,
    location   VARCHAR(150) NOT NULL,
    capacity   SMALLINT     NOT NULL,          -- seating / workstation capacity
    lab_type   VARCHAR(50)  NOT NULL,          -- e.g. Computer, Electronics, Physics
    CONSTRAINT pk_lab          PRIMARY KEY (lab_id),
    CONSTRAINT uq_lab_name     UNIQUE (lab_name),
    CONSTRAINT chk_lab_capacity CHECK (capacity > 0)
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- 2. equipment_category  (ER entity: Equipment Category)
-- ---------------------------------------------------------------------
CREATE TABLE equipment_category (
    category_id   INT          NOT NULL AUTO_INCREMENT,
    category_name VARCHAR(80)  NOT NULL,
    description   VARCHAR(255) NULL,
    CONSTRAINT pk_equipment_category PRIMARY KEY (category_id),
    CONSTRAINT uq_category_name      UNIQUE (category_name)
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- 3. supplier  (ER entity: Supplier)
-- ---------------------------------------------------------------------
CREATE TABLE supplier (
    supplier_id    INT          NOT NULL AUTO_INCREMENT,
    supplier_name  VARCHAR(120) NOT NULL,
    contact_number VARCHAR(15)  NOT NULL,
    email          VARCHAR(120) NULL,
    address        VARCHAR(255) NULL,
    CONSTRAINT pk_supplier           PRIMARY KEY (supplier_id),
    CONSTRAINT uq_supplier_name      UNIQUE (supplier_name),
    CONSTRAINT chk_supplier_contact  CHECK (REGEXP_LIKE(contact_number, '^[+]?[0-9]{10,14}$')),
    CONSTRAINT chk_supplier_email    CHECK (email IS NULL OR REGEXP_LIKE(email, '^[^@ ]+@[^@ ]+\\.[^@ ]+$'))
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- 4. student  (ER entity: Student)
-- ---------------------------------------------------------------------
CREATE TABLE student (
    student_id      INT          NOT NULL AUTO_INCREMENT,
    student_name    VARCHAR(100) NOT NULL,
    register_number VARCHAR(15)  NOT NULL,      -- university register number, e.g. 24BCE1012
    department      VARCHAR(60)  NOT NULL,
    year_of_study   TINYINT      NOT NULL,      -- ER attribute "Year"
    email           VARCHAR(120) NOT NULL,
    CONSTRAINT pk_student              PRIMARY KEY (student_id),
    CONSTRAINT uq_student_register_no  UNIQUE (register_number),
    CONSTRAINT uq_student_email        UNIQUE (email),
    CONSTRAINT chk_student_year        CHECK (year_of_study BETWEEN 1 AND 5),
    CONSTRAINT chk_student_email       CHECK (REGEXP_LIKE(email, '^[^@ ]+@[^@ ]+\\.[^@ ]+$'))
) ENGINE = InnoDB;

CREATE INDEX idx_student_department_year ON student (department, year_of_study);

-- ---------------------------------------------------------------------
-- 5. lab_staff  (ER entity: Lab Staff)
-- ---------------------------------------------------------------------
CREATE TABLE lab_staff (
    staff_id       INT          NOT NULL AUTO_INCREMENT,
    staff_name     VARCHAR(100) NOT NULL,
    designation    VARCHAR(60)  NOT NULL,
    department     VARCHAR(60)  NOT NULL,
    contact_number VARCHAR(15)  NOT NULL,
    email          VARCHAR(120) NOT NULL,
    CONSTRAINT pk_lab_staff          PRIMARY KEY (staff_id),
    CONSTRAINT uq_lab_staff_email    UNIQUE (email),
    CONSTRAINT chk_lab_staff_contact CHECK (REGEXP_LIKE(contact_number, '^[+]?[0-9]{10,14}$')),
    CONSTRAINT chk_lab_staff_email   CHECK (REGEXP_LIKE(email, '^[^@ ]+@[^@ ]+\\.[^@ ]+$'))
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- 6. purchase  (ER entity: Purchase)
--    supplier_id implements  Supplier 1 : N Purchase  (SUPPLIES)
-- ---------------------------------------------------------------------
CREATE TABLE purchase (
    purchase_id     INT           NOT NULL AUTO_INCREMENT,
    supplier_id     INT           NOT NULL,
    purchase_date   DATE          NOT NULL,
    invoice_number  VARCHAR(30)   NOT NULL,
    total_amount    DECIMAL(12,2) NOT NULL,     -- INR; DECIMAL, never FLOAT, for money
    purchase_status VARCHAR(20)   NOT NULL DEFAULT 'Ordered',
    CONSTRAINT pk_purchase              PRIMARY KEY (purchase_id),
    -- An invoice number is unique within the supplier that issued it.
    CONSTRAINT uq_purchase_supplier_invoice UNIQUE (supplier_id, invoice_number),
    CONSTRAINT chk_purchase_amount      CHECK (total_amount > 0),
    CONSTRAINT chk_purchase_status      CHECK (purchase_status IN ('Ordered', 'Received', 'Cancelled')),
    CONSTRAINT fk_purchase_supplier     FOREIGN KEY (supplier_id)
        REFERENCES supplier (supplier_id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE = InnoDB;

CREATE INDEX idx_purchase_date ON purchase (purchase_date);

-- ---------------------------------------------------------------------
-- 7. equipment  (ER entity: Equipment -- the central entity)
--    category_id implements Equipment Category 1 : N Equipment (CLASSIFIES)
--    lab_id      implements Lab                1 : N Equipment (CONTAINS)
--    purchase_id implements Purchase           1 : N Equipment (RESULTS_IN)
--
--    availability_status is the stored ER attribute Availability_Status.
--    It is changed only by the controlled transactions in
--    11_transaction_procedures.sql and audited by 09_validation_queries.sql.
-- ---------------------------------------------------------------------
CREATE TABLE equipment (
    equipment_id        INT          NOT NULL AUTO_INCREMENT,
    equipment_name      VARCHAR(120) NOT NULL,
    serial_number       VARCHAR(50)  NOT NULL,
    equipment_condition VARCHAR(20)  NOT NULL DEFAULT 'New',        -- ER attribute "Condition"
    availability_status VARCHAR(20)  NOT NULL DEFAULT 'Available',
    category_id         INT          NOT NULL,
    lab_id              INT          NOT NULL,
    purchase_id         INT          NOT NULL,
    CONSTRAINT pk_equipment               PRIMARY KEY (equipment_id),
    CONSTRAINT uq_equipment_serial_number UNIQUE (serial_number),
    CONSTRAINT chk_equipment_condition    CHECK (equipment_condition IN ('New', 'Good', 'Fair', 'Damaged')),
    CONSTRAINT chk_equipment_availability CHECK (availability_status IN
        ('Available', 'Allocated', 'Under Maintenance', 'Unavailable')),
    -- Business rule: damaged equipment can never be offered as available.
    CONSTRAINT chk_equipment_damaged_not_available CHECK
        (NOT (equipment_condition = 'Damaged' AND availability_status = 'Available')),
    CONSTRAINT fk_equipment_category FOREIGN KEY (category_id)
        REFERENCES equipment_category (category_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_equipment_lab      FOREIGN KEY (lab_id)
        REFERENCES lab (lab_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_equipment_purchase FOREIGN KEY (purchase_id)
        REFERENCES purchase (purchase_id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE = InnoDB;

CREATE INDEX idx_equipment_availability ON equipment (availability_status);
CREATE INDEX idx_equipment_name         ON equipment (equipment_name);

-- ---------------------------------------------------------------------
-- 8. equipment_allocation  (ER entity: Equipment Allocation)
--    equipment_id implements Equipment 1 : N Allocation (IS_ALLOCATED)
--    student_id   implements Student   1 : N Allocation (RECEIVES)
--    staff_id     implements Lab Staff 1 : N Allocation (ISSUES)
--
--    allocation_status: 'Issued' (equipment is out) or 'Returned'.
--    "Overdue" is NOT stored -- it is derived by comparing
--    expected_return_date with a date, so it can never be stale.
-- ---------------------------------------------------------------------
CREATE TABLE equipment_allocation (
    allocation_id        INT         NOT NULL AUTO_INCREMENT,
    equipment_id         INT         NOT NULL,
    student_id           INT         NOT NULL,
    staff_id             INT         NOT NULL,     -- staff member who issued the item
    allocation_date      DATE        NOT NULL,
    expected_return_date DATE        NOT NULL,
    allocation_status    VARCHAR(20) NOT NULL DEFAULT 'Issued',
    CONSTRAINT pk_equipment_allocation PRIMARY KEY (allocation_id),
    CONSTRAINT chk_allocation_status   CHECK (allocation_status IN ('Issued', 'Returned')),
    CONSTRAINT chk_allocation_dates    CHECK (expected_return_date >= allocation_date),
    CONSTRAINT fk_allocation_equipment FOREIGN KEY (equipment_id)
        REFERENCES equipment (equipment_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_allocation_student   FOREIGN KEY (student_id)
        REFERENCES student (student_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_allocation_staff     FOREIGN KEY (staff_id)
        REFERENCES lab_staff (staff_id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE = InnoDB;

-- Business rule: one equipment item cannot be issued to two students at
-- the same time. This functional UNIQUE index contains equipment_id only
-- for 'Issued' rows (NULL otherwise, and UNIQUE ignores NULLs), so any
-- number of 'Returned' rows may exist but at most ONE 'Issued' row per
-- equipment. Being a unique index, it also holds under concurrent
-- transactions (the second insert waits, then fails with error 1062).
CREATE UNIQUE INDEX uq_allocation_one_active_per_equipment
    ON equipment_allocation ((CASE WHEN allocation_status = 'Issued' THEN equipment_id END));

CREATE INDEX idx_allocation_status_due ON equipment_allocation (allocation_status, expected_return_date);
CREATE INDEX idx_allocation_date       ON equipment_allocation (allocation_date);

-- ---------------------------------------------------------------------
-- 9. equipment_return  (ER entity: Equipment Return)
--    allocation_id implements Allocation 1 : 1 Return (HAS_RETURN).
--    NOT NULL  -> every return belongs to exactly one allocation.
--    UNIQUE    -> an allocation has at most one return.
--    An allocation without a row here has simply not been returned yet.
-- ---------------------------------------------------------------------
CREATE TABLE equipment_return (
    return_id        INT          NOT NULL AUTO_INCREMENT,
    allocation_id    INT          NOT NULL,
    return_date      DATE         NOT NULL,
    return_condition VARCHAR(20)  NOT NULL,
    remarks          VARCHAR(255) NULL,
    CONSTRAINT pk_equipment_return    PRIMARY KEY (return_id),
    CONSTRAINT uq_return_allocation   UNIQUE (allocation_id),
    CONSTRAINT chk_return_condition   CHECK (return_condition IN ('Good', 'Fair', 'Damaged')),
    CONSTRAINT fk_return_allocation   FOREIGN KEY (allocation_id)
        REFERENCES equipment_allocation (allocation_id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- 10. maintenance  (ER entity: Maintenance)
--     equipment_id implements Equipment 1 : N Maintenance (UNDERGOES)
--     staff_id     implements Lab Staff 1 : N Maintenance (PERFORMS)
--
--     maintenance_cost is NULL while the cost is not yet known
--     (a 'Scheduled' job); a 'Completed' job must have a cost.
-- ---------------------------------------------------------------------
CREATE TABLE maintenance (
    maintenance_id     INT           NOT NULL AUTO_INCREMENT,
    equipment_id       INT           NOT NULL,
    staff_id           INT           NOT NULL,     -- staff member who performs the work
    maintenance_date   DATE          NOT NULL,
    maintenance_type   VARCHAR(20)   NOT NULL,
    maintenance_cost   DECIMAL(10,2) NULL,
    maintenance_status VARCHAR(20)   NOT NULL DEFAULT 'Scheduled',
    remarks            VARCHAR(255)  NULL,
    CONSTRAINT pk_maintenance             PRIMARY KEY (maintenance_id),
    CONSTRAINT chk_maintenance_type       CHECK (maintenance_type IN ('Preventive', 'Repair', 'Calibration')),
    CONSTRAINT chk_maintenance_status     CHECK (maintenance_status IN ('Scheduled', 'In Progress', 'Completed')),
    CONSTRAINT chk_maintenance_cost       CHECK (maintenance_cost >= 0),
    CONSTRAINT chk_maintenance_completed_cost CHECK
        (maintenance_status <> 'Completed' OR maintenance_cost IS NOT NULL),
    CONSTRAINT fk_maintenance_equipment   FOREIGN KEY (equipment_id)
        REFERENCES equipment (equipment_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_maintenance_staff       FOREIGN KEY (staff_id)
        REFERENCES lab_staff (staff_id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE = InnoDB;

CREATE INDEX idx_maintenance_status ON maintenance (maintenance_status);

-- Confirm: 10 base tables should be listed.
SELECT TABLE_NAME AS table_name, ENGINE AS engine
FROM   information_schema.TABLES
WHERE  TABLE_SCHEMA = 'smart_lab_equipment_db' AND TABLE_TYPE = 'BASE TABLE'
ORDER  BY TABLE_NAME;
