-- =====================================================================
-- File   : 06_join_queries.sql
-- Purpose: INNER JOIN, LEFT JOIN and multi-table joins.
-- Queries: Q28 - Q38
-- Run    : mysql -u <user> -p -t < sql/06_join_queries.sql
--
-- Every join below follows a declared foreign key
-- (child.fk_column = parent.primary_key). Joining a child to its parent
-- (N:1) never multiplies rows, so e.g. Q31 returns exactly one row per
-- allocation. Q38 shows how to combine TWO independent 1:N children of
-- equipment without row multiplication.
-- =====================================================================

USE smart_lab_equipment_db;

-- Q28 | INNER JOIN (2 tables): every purchase with the supplier it came from.
-- Join key: purchase.supplier_id -> supplier.supplier_id.
-- Expected: 7 rows; each purchase appears once.
SELECT p.purchase_id, p.invoice_number, p.purchase_date, p.total_amount,
       p.purchase_status, s.supplier_name, s.contact_number
FROM   purchase p
INNER JOIN supplier s ON s.supplier_id = p.supplier_id
ORDER  BY p.purchase_date;

-- Q29 | LEFT JOIN: every student with the number of allocations, INCLUDING
-- students who never borrowed anything. COUNT(a.allocation_id) counts
-- only matched rows, so unmatched students get 0 instead of 1.
-- Expected: 10 rows; Nisha Fernandes shows 0.
SELECT s.student_id, s.student_name, s.department,
       COUNT(a.allocation_id) AS allocation_count
FROM   student s
LEFT JOIN equipment_allocation a ON a.student_id = s.student_id
GROUP  BY s.student_id, s.student_name, s.department
ORDER  BY allocation_count DESC, s.student_name;

-- Q30 | INNER JOIN (3 tables): equipment with its category and laboratory.
-- Join keys: equipment.category_id -> equipment_category,
--            equipment.lab_id      -> lab.
-- Expected: 20 rows (one per equipment item).
SELECT e.equipment_id, e.equipment_name, e.serial_number,
       c.category_name, l.lab_name, l.location, e.availability_status
FROM   equipment e
INNER JOIN equipment_category c ON c.category_id = e.category_id
INNER JOIN lab                l ON l.lab_id      = e.lab_id
ORDER  BY l.lab_name, c.category_name, e.equipment_name;

-- Q31 | INNER JOIN (4 tables): complete allocation register - which
-- student received which equipment, issued by which staff member.
-- Expected: 20 rows (one per allocation).
SELECT a.allocation_id, a.allocation_date, a.expected_return_date, a.allocation_status,
       s.register_number, s.student_name,
       e.equipment_name, e.serial_number,
       ls.staff_name AS issued_by
FROM   equipment_allocation a
INNER JOIN student   s  ON s.student_id    = a.student_id
INNER JOIN equipment e  ON e.equipment_id  = a.equipment_id
INNER JOIN lab_staff ls ON ls.staff_id     = a.staff_id
ORDER  BY a.allocation_id;

-- Q32 | LEFT JOIN on the 1:1 HAS_RETURN relationship: every allocation
-- with its return details. Allocations not yet returned have no
-- equipment_return row, so the return columns come back NULL.
-- Expected: 20 rows; allocations 15-20 show 'Not yet returned'.
SELECT a.allocation_id, e.serial_number, a.allocation_date, a.expected_return_date,
       a.allocation_status,
       r.return_date,
       COALESCE(r.return_condition, 'Not yet returned') AS return_condition,
       r.remarks
FROM   equipment_allocation a
INNER JOIN equipment e        ON e.equipment_id  = a.equipment_id
LEFT  JOIN equipment_return r ON r.allocation_id = a.allocation_id
ORDER  BY a.allocation_id;

-- Q33 | INNER JOIN (3 tables): maintenance history - what was done to
-- which equipment and by which staff member.
-- Expected: 11 rows (one per maintenance record).
SELECT m.maintenance_id, m.maintenance_date, e.equipment_name, e.serial_number,
       m.maintenance_type, m.maintenance_status, m.maintenance_cost,
       ls.staff_name AS performed_by, m.remarks
FROM   maintenance m
INNER JOIN equipment e  ON e.equipment_id = m.equipment_id
INNER JOIN lab_staff ls ON ls.staff_id    = m.staff_id
ORDER  BY e.equipment_id, m.maintenance_date;

-- Q34 | LEFT JOIN ... IS NULL (anti-join): equipment that has NEVER
-- undergone maintenance.
-- Expected: 10 rows (equipment 4, 6, 7, 8, 10, 11, 14, 15, 18, 20).
SELECT e.equipment_id, e.equipment_name, e.serial_number
FROM   equipment e
LEFT JOIN maintenance m ON m.equipment_id = e.equipment_id
WHERE  m.maintenance_id IS NULL
ORDER  BY e.equipment_id;

-- Q35 | LEFT JOIN + GROUP BY: how many equipment items each purchase
-- brought in. The open order (purchase 7) has no equipment yet and still
-- appears with 0.
-- Expected: 7 rows; purchase 7 -> 0 items.
SELECT p.purchase_id, p.invoice_number, p.purchase_status,
       COUNT(e.equipment_id) AS items_received
FROM   purchase p
LEFT JOIN equipment e ON e.purchase_id = p.purchase_id
GROUP  BY p.purchase_id, p.invoice_number, p.purchase_status
ORDER  BY p.purchase_id;

-- Q36 | INNER JOIN (5 tables): full traceability of each equipment item -
-- category, lab, purchase invoice and supplier
-- (Supplier -> Purchase -> Equipment chain from the ER diagram).
-- Expected: 20 rows.
SELECT e.serial_number, e.equipment_name, c.category_name, l.lab_name,
       p.invoice_number, p.purchase_date, s.supplier_name
FROM   equipment e
INNER JOIN equipment_category c ON c.category_id = e.category_id
INNER JOIN lab                l ON l.lab_id      = e.lab_id
INNER JOIN purchase           p ON p.purchase_id = e.purchase_id
INNER JOIN supplier           s ON s.supplier_id = p.supplier_id
ORDER  BY s.supplier_name, p.purchase_date, e.serial_number;

-- Q37 | INNER JOIN with a cross-table comparison: returns that came back
-- AFTER the expected return date (late returns).
-- Expected: 2 rows -> allocation 13 (2 days late), allocation 4 (1 day late).
SELECT a.allocation_id, s.student_name, e.serial_number,
       a.expected_return_date, r.return_date,
       DATEDIFF(r.return_date, a.expected_return_date) AS days_late
FROM   equipment_allocation a
INNER JOIN equipment_return r ON r.allocation_id = a.allocation_id
INNER JOIN student          s ON s.student_id    = a.student_id
INNER JOIN equipment        e ON e.equipment_id  = a.equipment_id
WHERE  r.return_date > a.expected_return_date
ORDER  BY days_late DESC;

-- Q38 | Avoiding row multiplication: allocations AND maintenance per
-- equipment. Joining equipment to both child tables directly would pair
-- every allocation with every maintenance row (e.g. equipment 1 has
-- 2 allocations x 2 maintenance jobs = 4 rows, doubling both counts).
-- Each child is therefore aggregated first in a derived table, and the
-- one-row-per-equipment results are LEFT JOINed.
-- Expected: 20 rows; equipment 1 -> 2 allocations, 2 maintenance jobs,
--           maintenance cost 4250.00.
SELECT e.equipment_id, e.equipment_name,
       COALESCE(al.allocation_count, 0)  AS allocation_count,
       COALESCE(mt.maintenance_count, 0) AS maintenance_count,
       COALESCE(mt.maintenance_cost, 0)  AS maintenance_cost
FROM   equipment e
LEFT JOIN (SELECT equipment_id, COUNT(*) AS allocation_count
           FROM   equipment_allocation
           GROUP  BY equipment_id) al ON al.equipment_id = e.equipment_id
LEFT JOIN (SELECT equipment_id, COUNT(*) AS maintenance_count,
                  SUM(maintenance_cost) AS maintenance_cost
           FROM   maintenance
           GROUP  BY equipment_id) mt ON mt.equipment_id = e.equipment_id
ORDER  BY e.equipment_id;
