-- =====================================================================
-- File   : 07_subqueries.sql
-- Purpose: Scalar, IN / NOT IN, EXISTS / NOT EXISTS, correlated
--          subqueries, derived tables and comparisons with aggregates.
-- Queries: Q39 - Q49
-- Run    : mysql -u <user> -p -t < sql/07_subqueries.sql
-- =====================================================================

USE smart_lab_equipment_db;

-- Q39 | SCALAR subquery in WHERE (comparison against an aggregate):
-- maintenance jobs that cost more than the average maintenance cost.
-- The inner query returns one value: AVG over the 9 costed jobs = 2238.89
-- (NULL costs of scheduled jobs are ignored by AVG).
-- Expected: 3 rows -> maintenance 8 (8500.00), 5 (3200.00), 7 (2750.00).
SELECT m.maintenance_id, e.serial_number, m.maintenance_type, m.maintenance_cost
FROM   maintenance m
JOIN   equipment e ON e.equipment_id = m.equipment_id
WHERE  m.maintenance_cost > (SELECT AVG(maintenance_cost) FROM maintenance)
ORDER  BY m.maintenance_cost DESC;

-- Q40 | SCALAR subquery in the SELECT list: each category's share of the
-- whole inventory. The subquery (total equipment = 20) is evaluated once.
-- Expected: 6 rows; e.g. Multimeter 4 items = 20.0 %.
SELECT c.category_name,
       COUNT(*) AS equipment_count,
       ROUND(100 * COUNT(*) / (SELECT COUNT(*) FROM equipment), 1) AS percent_of_inventory
FROM   equipment_category c
JOIN   equipment e ON e.category_id = c.category_id
GROUP  BY c.category_id, c.category_name
ORDER  BY equipment_count DESC, c.category_name;

-- Q41 | IN subquery: students who are holding equipment right now.
-- The inner query lists student_ids of 'Issued' allocations.
-- Expected: 6 rows -> Aarav, Diya, Kabir, Rohan, Vikram, Ishaan.
SELECT student_id, register_number, student_name, department
FROM   student
WHERE  student_id IN (SELECT student_id
                      FROM   equipment_allocation
                      WHERE  allocation_status = 'Issued')
ORDER  BY student_id;

-- Q42 | NOT IN subquery: students who have never borrowed any equipment.
-- (Safe because equipment_allocation.student_id is NOT NULL; NOT IN
--  returns nothing if the subquery yields a NULL.)
-- Expected: 1 row -> Nisha Fernandes.
SELECT student_id, register_number, student_name
FROM   student
WHERE  student_id NOT IN (SELECT student_id FROM equipment_allocation);

-- Q43 | EXISTS (correlated): equipment that has EVER been returned damaged.
-- For each equipment row e, the inner query looks for a damaged return
-- of an allocation of THAT equipment (a.equipment_id = e.equipment_id).
-- Expected: 2 rows -> equipment 3 (OSC-MS2-0003), 9 (MCU-ARD-0009).
SELECT e.equipment_id, e.serial_number, e.equipment_name, e.availability_status
FROM   equipment e
WHERE  EXISTS (SELECT 1
               FROM   equipment_allocation a
               JOIN   equipment_return r ON r.allocation_id = a.allocation_id
               WHERE  a.equipment_id = e.equipment_id
                 AND  r.return_condition = 'Damaged')
ORDER  BY e.equipment_id;

-- Q44 | NOT EXISTS (correlated): equipment with NO maintenance history.
-- Same answer as the LEFT JOIN anti-join in Q34, written as a subquery.
-- Expected: 10 rows (equipment 4, 6, 7, 8, 10, 11, 14, 15, 18, 20).
SELECT e.equipment_id, e.serial_number, e.equipment_name
FROM   equipment e
WHERE  NOT EXISTS (SELECT 1
                   FROM   maintenance m
                   WHERE  m.equipment_id = e.equipment_id)
ORDER  BY e.equipment_id;

-- Q45 | CORRELATED subquery: maintenance jobs that cost more than the
-- average for THEIR OWN maintenance type. The inner AVG is recomputed
-- for each outer row using m.maintenance_type.
-- Type averages: Calibration 1400.00, Preventive 500.00, Repair 4816.67.
-- Expected: 4 rows -> maintenance 1 and 2 (1500.00 > 1400.00),
--           3 (600.00 > 500.00), 8 (8500.00 > 4816.67).
SELECT m.maintenance_id, m.maintenance_type, m.maintenance_cost,
       (SELECT ROUND(AVG(m2.maintenance_cost), 2)
        FROM   maintenance m2
        WHERE  m2.maintenance_type = m.maintenance_type) AS type_average
FROM   maintenance m
WHERE  m.maintenance_cost > (SELECT AVG(m2.maintenance_cost)
                             FROM   maintenance m2
                             WHERE  m2.maintenance_type = m.maintenance_type)
ORDER  BY m.maintenance_type, m.maintenance_id;

-- Q46 | Comparison against an aggregate of aggregates (derived table):
-- equipment whose TOTAL maintenance cost is above the average total
-- maintenance cost per costed equipment item.
-- Inner derived table: total cost per equipment (8 items have a cost);
-- their average = 20150.00 / 8 = 2518.75.
-- Expected: 3 rows -> equipment 3 (8500.00), 1 (4250.00), 19 (3200.00).
SELECT e.equipment_id, e.serial_number, e.equipment_name,
       SUM(m.maintenance_cost) AS total_maintenance_cost
FROM   equipment e
JOIN   maintenance m ON m.equipment_id = e.equipment_id
GROUP  BY e.equipment_id, e.serial_number, e.equipment_name
HAVING SUM(m.maintenance_cost) >
       (SELECT AVG(per_item.total_cost)
        FROM  (SELECT SUM(maintenance_cost) AS total_cost
               FROM   maintenance
               GROUP  BY equipment_id) AS per_item)
ORDER  BY total_maintenance_cost DESC;

-- Q47 | Benchmark comparison: students whose number of allocations is
-- above the average number of allocations per registered student
-- (20 allocations / 10 students = 2.0).
-- Expected: 4 rows -> Aarav Menon 4, Diya Raghavan 3, Ishaan Rao 3,
--           Vikram Joshi 3.
SELECT s.student_id, s.student_name, COUNT(*) AS allocation_count
FROM   student s
JOIN   equipment_allocation a ON a.student_id = s.student_id
GROUP  BY s.student_id, s.student_name
HAVING COUNT(*) > (SELECT COUNT(*) FROM equipment_allocation)
                / (SELECT COUNT(*) FROM student)
ORDER  BY allocation_count DESC, s.student_name;

-- Q48 | CORRELATED scalar subqueries in the SELECT list: for every
-- equipment item, the date it was last issued and last serviced.
-- NULL means "never".
-- Expected: 20 rows; e.g. equipment 1 -> last issued 2026-10-01,
--           last maintenance 2026-09-02.
SELECT e.equipment_id, e.serial_number,
       (SELECT MAX(a.allocation_date)
        FROM   equipment_allocation a
        WHERE  a.equipment_id = e.equipment_id)  AS last_issued_on,
       (SELECT MAX(m.maintenance_date)
        FROM   maintenance m
        WHERE  m.equipment_id = e.equipment_id
          AND  m.maintenance_status = 'Completed') AS last_maintenance_completed
FROM   equipment e
ORDER  BY e.equipment_id;

-- Q49 | Comparison with ALL: the purchase(s) whose amount is greater
-- than or equal to every other purchase amount (the largest purchase).
-- Expected: 1 row -> ASI-2025-0141, 105000.00.
SELECT p.purchase_id, p.invoice_number, p.total_amount, s.supplier_name
FROM   purchase p
JOIN   supplier s ON s.supplier_id = p.supplier_id
WHERE  p.total_amount >= ALL (SELECT total_amount FROM purchase);
