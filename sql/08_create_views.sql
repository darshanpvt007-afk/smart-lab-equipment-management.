-- =====================================================================
-- File   : 08_create_views.sql
-- Purpose: Reusable views over the relational schema + demo queries.
-- Views  : vw_equipment_inventory, vw_outstanding_allocations,
--          vw_maintenance_history, vw_allocation_history
-- Queries: Q50 - Q55 (SELECTs that use the views)
-- Run    : mysql -u <user> -p -t < sql/08_create_views.sql
--
-- A view is a stored SELECT (a "virtual table"). It holds no data of
-- its own: each time it is queried it re-runs its SELECT, so it always
-- shows the current table contents. A view does NOT send alerts or run
-- on a schedule; it only simplifies and standardises queries.
--
-- CREATE OR REPLACE makes this script safe to re-run.
-- MySQL views cannot use session variables (@ref_date), so date-based
-- filtering (e.g. "overdue") is done in the query that uses the view.
-- =====================================================================

USE smart_lab_equipment_db;

-- ---------------------------------------------------------------------
-- View 1: vw_equipment_inventory
-- One row per equipment item with its category, laboratory and source
-- (purchase + supplier). All joins are child -> parent (N:1), so the view
-- has exactly as many rows as the equipment table.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_equipment_inventory AS
SELECT e.equipment_id,
       e.equipment_name,
       e.serial_number,
       c.category_name,
       l.lab_name,
       l.location            AS lab_location,
       e.equipment_condition,
       e.availability_status,
       p.invoice_number,
       p.purchase_date,
       s.supplier_name
FROM   equipment e
JOIN   equipment_category c ON c.category_id = e.category_id
JOIN   lab                l ON l.lab_id      = e.lab_id
JOIN   purchase           p ON p.purchase_id = e.purchase_id
JOIN   supplier           s ON s.supplier_id = p.supplier_id;

-- ---------------------------------------------------------------------
-- View 2: vw_outstanding_allocations
-- Allocations whose equipment has not come back yet ('Issued'), with who
-- holds it, where it belongs and who issued it.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_outstanding_allocations AS
SELECT a.allocation_id,
       a.allocation_date,
       a.expected_return_date,
       s.student_id,
       s.register_number,
       s.student_name,
       s.email               AS student_email,
       e.equipment_id,
       e.equipment_name,
       e.serial_number,
       l.lab_name,
       ls.staff_name         AS issued_by
FROM   equipment_allocation a
JOIN   student   s  ON s.student_id   = a.student_id
JOIN   equipment e  ON e.equipment_id = a.equipment_id
JOIN   lab       l  ON l.lab_id       = e.lab_id
JOIN   lab_staff ls ON ls.staff_id    = a.staff_id
WHERE  a.allocation_status = 'Issued';

-- ---------------------------------------------------------------------
-- View 3: vw_maintenance_history
-- Every maintenance record with the equipment, its lab and the staff
-- member who performed the work.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_maintenance_history AS
SELECT m.maintenance_id,
       m.maintenance_date,
       e.equipment_id,
       e.equipment_name,
       e.serial_number,
       l.lab_name,
       m.maintenance_type,
       m.maintenance_status,
       m.maintenance_cost,
       ls.staff_name         AS performed_by,
       m.remarks
FROM   maintenance m
JOIN   equipment e  ON e.equipment_id = m.equipment_id
JOIN   lab       l  ON l.lab_id       = e.lab_id
JOIN   lab_staff ls ON ls.staff_id    = m.staff_id;

-- ---------------------------------------------------------------------
-- View 4: vw_allocation_history
-- The full usage history: every allocation with its (optional) return.
-- LEFT JOIN keeps allocations that have no return row yet.
-- days_late is NULL for unreturned items, 0 for on-time returns.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_allocation_history AS
SELECT a.allocation_id,
       s.register_number,
       s.student_name,
       e.serial_number,
       e.equipment_name,
       ls.staff_name         AS issued_by,
       a.allocation_date,
       a.expected_return_date,
       a.allocation_status,
       r.return_date,
       r.return_condition,
       r.remarks             AS return_remarks,
       CASE WHEN r.return_date IS NULL THEN NULL
            ELSE GREATEST(DATEDIFF(r.return_date, a.expected_return_date), 0)
       END                   AS days_late
FROM   equipment_allocation a
JOIN   student   s  ON s.student_id   = a.student_id
JOIN   equipment e  ON e.equipment_id = a.equipment_id
JOIN   lab_staff ls ON ls.staff_id    = a.staff_id
LEFT JOIN equipment_return r ON r.allocation_id = a.allocation_id;

-- =====================================================================
-- Queries that use the views
-- =====================================================================

SET @ref_date = DATE '2026-10-10';

-- Q50 | View 1 with WHERE: available equipment in the Applied Physics Lab.
-- Expected: 4 rows (CLM-32-0007, DMM-17B-0006, OPT-LDK-0020, OPT-SPM-0019).
SELECT serial_number, equipment_name, category_name, equipment_condition
FROM   vw_equipment_inventory
WHERE  lab_name = 'Applied Physics Lab'
  AND  availability_status = 'Available'
ORDER  BY serial_number;

-- Q51 | View 1 with GROUP BY: availability breakdown per laboratory.
-- Expected: 4 rows, e.g. Computer Networks Lab -> 4 items, 2 available.
SELECT lab_name,
       COUNT(*)                                     AS total_items,
       SUM(availability_status = 'Available')       AS available,
       SUM(availability_status = 'Allocated')       AS allocated,
       SUM(availability_status = 'Under Maintenance') AS under_maintenance,
       SUM(availability_status = 'Unavailable')     AS unavailable
FROM   vw_equipment_inventory
GROUP  BY lab_name
ORDER  BY lab_name;

-- Q52 | View 2: all equipment currently out with students.
-- Expected: 6 rows (allocations 15 - 20).
SELECT allocation_id, register_number, student_name, serial_number,
       lab_name, issued_by, expected_return_date
FROM   vw_outstanding_allocations
ORDER  BY expected_return_date;

-- Q53 | View 2 + date filter: OVERDUE items on the reference date.
-- Expected on 2026-10-10: 3 rows (allocations 15, 16, 17).
-- Live version: replace @ref_date with CURDATE().
SELECT allocation_id, student_name, student_email, serial_number,
       expected_return_date,
       DATEDIFF(@ref_date, expected_return_date) AS days_overdue
FROM   vw_outstanding_allocations
WHERE  expected_return_date < @ref_date
ORDER  BY days_overdue DESC;

-- Q54 | View 3: maintenance history of one item (OSC-DS1-0001).
-- Expected: 2 rows (calibration 2026-06-15, repair 2026-09-02).
SELECT maintenance_date, maintenance_type, maintenance_status,
       maintenance_cost, performed_by, remarks
FROM   vw_maintenance_history
WHERE  serial_number = 'OSC-DS1-0001'
ORDER  BY maintenance_date;

-- Q55 | View 4: complete usage history of one student (Aarav Menon),
-- showing returned and still-issued allocations together.
-- Expected: 4 rows; allocation 4 was 1 day late; allocation 17 has no
--           return yet (return columns NULL).
SELECT allocation_id, serial_number, equipment_name, allocation_date,
       expected_return_date, allocation_status, return_date,
       return_condition, days_late
FROM   vw_allocation_history
WHERE  register_number = '24BCE1012'
ORDER  BY allocation_date;
