-- =====================================================================
-- File   : 09_validation_queries.sql
-- Purpose: Data-integrity and business-rule audit queries.
-- Checks : V01 - V16
-- Run    : mysql -u <user> -p -t < sql/09_validation_queries.sql
--
-- HOW TO READ THE RESULTS
--   V01 - V14 look for VIOLATIONS. On correct data each returns ZERO rows
--             (V01 returns one summary row whose counts are all 0).
--             Many of them can never fail because a constraint already
--             blocks the bad data; they are kept as audits that prove it
--             and that would catch drift if a constraint were removed.
--   V15 - V16 are "to investigate" reports. They return rows by design
--             (overdue loans, overdue scheduled maintenance).
--
-- Rules that the CREATE TABLE constraints CANNOT express (they compare
-- rows of different tables, or rows of the same table with each other)
-- are checked here: V05, V06, V07, V09, V10, V11, V12, V13.
-- =====================================================================

USE smart_lab_equipment_db;

SET @ref_date = DATE '2026-10-10';   -- live use: CURDATE()

-- V01 | Orphaned foreign keys (child rows whose parent does not exist).
-- Prevented by the FOREIGN KEY constraints; every count must be 0.
SELECT
  (SELECT COUNT(*) FROM purchase p             LEFT JOIN supplier s            ON s.supplier_id  = p.supplier_id   WHERE s.supplier_id  IS NULL) AS purchase_without_supplier,
  (SELECT COUNT(*) FROM equipment e            LEFT JOIN equipment_category c  ON c.category_id  = e.category_id   WHERE c.category_id  IS NULL) AS equipment_without_category,
  (SELECT COUNT(*) FROM equipment e            LEFT JOIN lab l                 ON l.lab_id       = e.lab_id        WHERE l.lab_id       IS NULL) AS equipment_without_lab,
  (SELECT COUNT(*) FROM equipment e            LEFT JOIN purchase p            ON p.purchase_id  = e.purchase_id   WHERE p.purchase_id  IS NULL) AS equipment_without_purchase,
  (SELECT COUNT(*) FROM equipment_allocation a LEFT JOIN equipment e           ON e.equipment_id = a.equipment_id  WHERE e.equipment_id IS NULL) AS allocation_without_equipment,
  (SELECT COUNT(*) FROM equipment_allocation a LEFT JOIN student s             ON s.student_id   = a.student_id    WHERE s.student_id   IS NULL) AS allocation_without_student,
  (SELECT COUNT(*) FROM equipment_allocation a LEFT JOIN lab_staff ls          ON ls.staff_id    = a.staff_id      WHERE ls.staff_id    IS NULL) AS allocation_without_staff,
  (SELECT COUNT(*) FROM equipment_return r     LEFT JOIN equipment_allocation a ON a.allocation_id = r.allocation_id WHERE a.allocation_id IS NULL) AS return_without_allocation,
  (SELECT COUNT(*) FROM maintenance m          LEFT JOIN equipment e           ON e.equipment_id = m.equipment_id  WHERE e.equipment_id IS NULL) AS maintenance_without_equipment,
  (SELECT COUNT(*) FROM maintenance m          LEFT JOIN lab_staff ls          ON ls.staff_id    = m.staff_id      WHERE ls.staff_id    IS NULL) AS maintenance_without_staff;

-- V02 | Duplicate student register numbers (prevented by UNIQUE). Expected: 0 rows.
SELECT register_number, COUNT(*) AS occurrences
FROM   student
GROUP  BY register_number
HAVING COUNT(*) > 1;

-- V03 | Duplicate equipment serial numbers (prevented by UNIQUE). Expected: 0 rows.
SELECT serial_number, COUNT(*) AS occurrences
FROM   equipment
GROUP  BY serial_number
HAVING COUNT(*) > 1;

-- V04 | Allocations whose expected return date is before the allocation
-- date (prevented by CHECK chk_allocation_dates). Expected: 0 rows.
SELECT allocation_id, allocation_date, expected_return_date
FROM   equipment_allocation
WHERE  expected_return_date < allocation_date;

-- V05 | Invalid dates: records dated after the reference date that
-- describe something that has already happened. (MySQL CHECK constraints
-- cannot use CURDATE(), so this rule is audited here.)
-- Scheduled maintenance MAY be in the future and is therefore excluded.
-- Expected: 0 rows.
SELECT 'purchase'   AS table_name, purchase_id   AS record_id, purchase_date   AS record_date FROM purchase             WHERE purchase_date   > @ref_date
UNION ALL
SELECT 'allocation',               allocation_id,              allocation_date                FROM equipment_allocation WHERE allocation_date > @ref_date
UNION ALL
SELECT 'return',                   return_id,                  return_date                    FROM equipment_return     WHERE return_date     > @ref_date
UNION ALL
SELECT 'maintenance',              maintenance_id,             maintenance_date               FROM maintenance          WHERE maintenance_date > @ref_date AND maintenance_status <> 'Scheduled';

-- V06 | Return records inconsistent with their allocation:
--   (a) returned before it was issued, or
--   (b) the allocation is still marked 'Issued' although a return exists.
-- Expected: 0 rows.
SELECT r.return_id, a.allocation_id, a.allocation_date, r.return_date, a.allocation_status,
       CASE WHEN r.return_date < a.allocation_date THEN 'Returned before issue date'
            ELSE 'Return exists but allocation still Issued' END AS problem
FROM   equipment_return r
JOIN   equipment_allocation a ON a.allocation_id = r.allocation_id
WHERE  r.return_date < a.allocation_date
   OR  a.allocation_status <> 'Returned';

-- V07 | Allocations marked 'Returned' that have no return record.
-- Expected: 0 rows.
SELECT a.allocation_id, a.equipment_id, a.allocation_status
FROM   equipment_allocation a
LEFT JOIN equipment_return r ON r.allocation_id = a.allocation_id
WHERE  a.allocation_status = 'Returned'
  AND  r.return_id IS NULL;

-- V08 | ALLOCATION CONFLICT: equipment with more than one 'Issued'
-- allocation at the same time (prevented by the functional UNIQUE index
-- uq_allocation_one_active_per_equipment). Expected: 0 rows.
SELECT equipment_id, COUNT(*) AS active_allocations
FROM   equipment_allocation
WHERE  allocation_status = 'Issued'
GROUP  BY equipment_id
HAVING COUNT(*) > 1;

-- V09 | ALLOCATION CONFLICT (history): two allocations of the same
-- equipment whose loan periods overlap. A loan period runs from
-- allocation_date to the return date (or is still open if not returned).
-- Expected: 0 rows.
SELECT a1.equipment_id, a1.allocation_id AS first_allocation, a2.allocation_id AS second_allocation,
       a1.allocation_date AS first_issued, r1.return_date AS first_returned,
       a2.allocation_date AS second_issued
FROM   equipment_allocation a1
LEFT JOIN equipment_return r1 ON r1.allocation_id = a1.allocation_id
JOIN   equipment_allocation a2
       ON  a2.equipment_id    = a1.equipment_id
       AND a2.allocation_id  <> a1.allocation_id
       AND a2.allocation_date >= a1.allocation_date
WHERE  r1.return_id IS NULL                        -- first loan never closed
   OR  a2.allocation_date < r1.return_date;        -- second loan began before the first was returned

-- V10 | Stored availability disagrees with the allocation history:
--   'Allocated' must have exactly one 'Issued' allocation and vice versa.
-- Expected: 0 rows.
SELECT e.equipment_id, e.serial_number, e.availability_status,
       COUNT(a.allocation_id) AS issued_allocations
FROM   equipment e
LEFT JOIN equipment_allocation a
       ON a.equipment_id = e.equipment_id AND a.allocation_status = 'Issued'
GROUP  BY e.equipment_id, e.serial_number, e.availability_status
HAVING (e.availability_status =  'Allocated' AND COUNT(a.allocation_id) = 0)
    OR (e.availability_status <> 'Allocated' AND COUNT(a.allocation_id) > 0);

-- V11 | Stored availability disagrees with maintenance:
--   'Under Maintenance' requires an 'In Progress' job, and an
--   'In Progress' job requires the item to be 'Under Maintenance'.
-- Expected: 0 rows.
SELECT e.equipment_id, e.serial_number, e.availability_status,
       COUNT(m.maintenance_id) AS jobs_in_progress
FROM   equipment e
LEFT JOIN maintenance m
       ON m.equipment_id = e.equipment_id AND m.maintenance_status = 'In Progress'
GROUP  BY e.equipment_id, e.serial_number, e.availability_status
HAVING (e.availability_status =  'Under Maintenance' AND COUNT(m.maintenance_id) = 0)
    OR (e.availability_status <> 'Under Maintenance' AND COUNT(m.maintenance_id) > 0);

-- V12 | Damaged equipment offered as Available (prevented by CHECK
-- chk_equipment_damaged_not_available), or an item whose latest return
-- was 'Damaged' but which was put back into service without any
-- maintenance completed after that return. Expected: 0 rows.
SELECT e.equipment_id, e.serial_number, e.equipment_condition, e.availability_status
FROM   equipment e
WHERE  (e.equipment_condition = 'Damaged' AND e.availability_status = 'Available')
   OR  (e.availability_status IN ('Available', 'Allocated')
        AND EXISTS (SELECT 1
                    FROM   equipment_allocation a
                    JOIN   equipment_return r ON r.allocation_id = a.allocation_id
                    WHERE  a.equipment_id = e.equipment_id
                      AND  r.return_condition = 'Damaged'
                      AND  NOT EXISTS (SELECT 1 FROM maintenance m
                                       WHERE  m.equipment_id = e.equipment_id
                                         AND  m.maintenance_status = 'Completed'
                                         AND  m.maintenance_date >= r.return_date)));

-- V13 | Maintenance records with invalid cost or dates:
--   negative cost, a Completed job without a cost, or a job dated before
--   the equipment was purchased. Expected: 0 rows.
SELECT m.maintenance_id, m.equipment_id, m.maintenance_date, p.purchase_date,
       m.maintenance_status, m.maintenance_cost
FROM   maintenance m
JOIN   equipment e ON e.equipment_id = m.equipment_id
JOIN   purchase  p ON p.purchase_id  = e.purchase_id
WHERE  m.maintenance_cost < 0
   OR  (m.maintenance_status = 'Completed' AND m.maintenance_cost IS NULL)
   OR  m.maintenance_date < p.purchase_date;

-- V14 | Equipment with missing or invalid associations:
--   NULL foreign keys (prevented by NOT NULL), equipment linked to a
--   purchase that has not been 'Received', or equipment allocated
--   before it was purchased. Expected: 0 rows.
SELECT e.equipment_id, e.serial_number, p.purchase_status, p.purchase_date,
       MIN(a.allocation_date) AS first_allocation
FROM   equipment e
LEFT JOIN purchase p ON p.purchase_id = e.purchase_id
LEFT JOIN equipment_allocation a ON a.equipment_id = e.equipment_id
GROUP  BY e.equipment_id, e.serial_number, e.category_id, e.lab_id, e.purchase_id,
          p.purchase_status, p.purchase_date
HAVING e.category_id IS NULL OR e.lab_id IS NULL OR e.purchase_id IS NULL
    OR p.purchase_status <> 'Received'
    OR MIN(a.allocation_date) < p.purchase_date;

-- V15 | TO INVESTIGATE: outstanding allocations past their expected
-- return date. Expected on 2026-10-10: 3 rows (allocations 15, 16, 17).
SELECT a.allocation_id, s.student_name, s.email, e.serial_number,
       a.expected_return_date, DATEDIFF(@ref_date, a.expected_return_date) AS days_overdue
FROM   equipment_allocation a
JOIN   student   s ON s.student_id   = a.student_id
JOIN   equipment e ON e.equipment_id = a.equipment_id
WHERE  a.allocation_status = 'Issued'
  AND  a.expected_return_date < @ref_date
ORDER  BY days_overdue DESC;

-- V16 | TO INVESTIGATE: maintenance still 'Scheduled' although its date
-- has passed. Expected on 2026-10-10: 0 rows (both scheduled jobs are
-- dated 2026-10-15 and 2026-10-20).
SELECT maintenance_id, equipment_id, maintenance_date, maintenance_type
FROM   maintenance
WHERE  maintenance_status = 'Scheduled'
  AND  maintenance_date < @ref_date;
