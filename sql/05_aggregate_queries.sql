-- =====================================================================
-- File   : 05_aggregate_queries.sql
-- Purpose: Aggregate functions (COUNT, SUM, AVG, MIN, MAX),
--          GROUP BY and HAVING.
-- Queries: Q16 - Q27
-- Run    : mysql -u <user> -p -t < sql/05_aggregate_queries.sql
--
-- Remember:
--   WHERE  filters individual ROWS  before grouping.
--   HAVING filters whole GROUPS     after grouping (can use aggregates).
-- All queries are valid under MySQL 8's default ONLY_FULL_GROUP_BY mode:
-- every non-aggregated column in SELECT appears in GROUP BY.
-- =====================================================================

USE smart_lab_equipment_db;

-- Q16 | COUNT + GROUP BY: number of equipment items in each laboratory.
-- Expected: 4 rows -> Embedded Systems 6, Applied Physics 5,
--           Electronics and Circuits 5, Computer Networks 4.
SELECT l.lab_id, l.lab_name, COUNT(e.equipment_id) AS equipment_count
FROM   lab l
JOIN   equipment e ON e.lab_id = l.lab_id
GROUP  BY l.lab_id, l.lab_name
ORDER  BY equipment_count DESC, l.lab_name;

-- Q17 | COUNT + GROUP BY: number of equipment items in each category.
-- Expected: 6 rows -> Microcontroller Kit 4, Multimeter 4, Networking
--           Device 4, Oscilloscope 3, Power Supply 3, Optical Instrument 2.
SELECT c.category_id, c.category_name, COUNT(e.equipment_id) AS equipment_count
FROM   equipment_category c
JOIN   equipment e ON e.category_id = c.category_id
GROUP  BY c.category_id, c.category_name
ORDER  BY equipment_count DESC, c.category_name;

-- Q18 | COUNT + GROUP BY: number of allocations per student, plus the
-- first and last time each student borrowed something (MIN / MAX).
-- Expected: 9 rows (Nisha Fernandes has never borrowed, so she is absent
--           from an inner join -- see Q29 for the LEFT JOIN version).
--           Aarav Menon has the most allocations (4).
SELECT s.student_id, s.student_name,
       COUNT(*)               AS allocation_count,
       MIN(a.allocation_date) AS first_allocation,
       MAX(a.allocation_date) AS latest_allocation
FROM   student s
JOIN   equipment_allocation a ON a.student_id = s.student_id
GROUP  BY s.student_id, s.student_name
ORDER  BY allocation_count DESC, s.student_name;

-- Q19 | SUM + COUNT + GROUP BY with a WHERE row filter: total spent with
-- each supplier on purchases that have actually been received.
-- WHERE removes the 'Ordered' purchase rows BEFORE they are grouped.
-- Expected: 4 rows -> Apex 208500.00 (2 purchases), Orbit 72500.00 (1),
--           Zenith 68700.00 (1), TechNova 39000.00 (2).
SELECT sp.supplier_id, sp.supplier_name,
       COUNT(p.purchase_id) AS purchases_received,
       SUM(p.total_amount)  AS total_expenditure
FROM   supplier sp
JOIN   purchase p ON p.supplier_id = sp.supplier_id
WHERE  p.purchase_status = 'Received'
GROUP  BY sp.supplier_id, sp.supplier_name
ORDER  BY total_expenditure DESC;

-- Q20 | AVG, MIN, MAX + GROUP BY: maintenance cost statistics per type.
-- COUNT(*) counts all rows; COUNT(maintenance_cost) and AVG ignore NULL
-- (scheduled jobs whose cost is not known yet).
-- Expected: Calibration 4 jobs / 3 costed / avg 1400.00,
--           Preventive  3 / 3 / avg 500.00,
--           Repair      4 / 3 / avg 4816.67.
SELECT maintenance_type,
       COUNT(*)                        AS total_jobs,
       COUNT(maintenance_cost)         AS jobs_with_cost,
       ROUND(AVG(maintenance_cost), 2) AS average_cost,
       MIN(maintenance_cost)           AS minimum_cost,
       MAX(maintenance_cost)           AS maximum_cost,
       SUM(maintenance_cost)           AS total_cost
FROM   maintenance
GROUP  BY maintenance_type
ORDER  BY maintenance_type;

-- Q21 | COUNT + GROUP BY: maintenance records by status.
-- Expected: Completed 7, In Progress 2, Scheduled 2.
SELECT maintenance_status, COUNT(*) AS record_count
FROM   maintenance
GROUP  BY maintenance_status
ORDER  BY record_count DESC;

-- Q22 | HAVING: students who have borrowed equipment MORE than twice.
-- The condition uses COUNT(*), so it must be in HAVING, not WHERE.
-- Expected: 4 rows -> Aarav Menon 4, Diya Raghavan 3, Ishaan Rao 3,
--           Vikram Joshi 3.
SELECT s.student_id, s.student_name, COUNT(*) AS allocation_count
FROM   student s
JOIN   equipment_allocation a ON a.student_id = s.student_id
GROUP  BY s.student_id, s.student_name
HAVING COUNT(*) > 2
ORDER  BY allocation_count DESC, s.student_name;

-- Q23 | HAVING: laboratories holding more than 4 equipment items.
-- Expected: 3 rows -> Embedded Systems 6, Applied Physics 5,
--           Electronics and Circuits 5 (Computer Networks, 4, is excluded).
SELECT l.lab_name, COUNT(*) AS equipment_count
FROM   lab l
JOIN   equipment e ON e.lab_id = l.lab_id
GROUP  BY l.lab_id, l.lab_name
HAVING COUNT(*) > 4
ORDER  BY equipment_count DESC, l.lab_name;

-- Q24 | WHERE + GROUP BY + HAVING together: suppliers with more than one
-- non-cancelled purchase whose combined value exceeds 50,000.
-- Expected: 2 rows -> Apex (2 purchases, 208500.00),
--           Orbit (2 purchases incl. the open order, 118500.00).
--           TechNova also has 2 purchases but only 39000.00 in total.
SELECT sp.supplier_name,
       COUNT(*)            AS purchase_count,
       SUM(p.total_amount) AS total_value
FROM   supplier sp
JOIN   purchase p ON p.supplier_id = sp.supplier_id
WHERE  p.purchase_status <> 'Cancelled'
GROUP  BY sp.supplier_id, sp.supplier_name
HAVING COUNT(*) > 1 AND SUM(p.total_amount) > 50000
ORDER  BY total_value DESC;

-- Q25 | Aggregates without GROUP BY: one summary row over all purchases.
-- Expected: 7 purchases, total 434700.00, average 62100.00,
--           smallest 14800.00, largest 105000.00, dates 2025-06-10 .. 2026-09-28.
SELECT COUNT(*)                   AS purchase_count,
       SUM(total_amount)          AS total_amount,
       ROUND(AVG(total_amount),2) AS average_amount,
       MIN(total_amount)          AS smallest_purchase,
       MAX(total_amount)          AS largest_purchase,
       MIN(purchase_date)         AS first_purchase,
       MAX(purchase_date)         AS latest_purchase
FROM   purchase;

-- Q26 | COUNT + GROUP BY: current availability summary of the inventory.
-- Expected: Available 11, Allocated 6, Under Maintenance 2, Unavailable 1.
SELECT availability_status, COUNT(*) AS equipment_count
FROM   equipment
GROUP  BY availability_status
ORDER  BY equipment_count DESC;

-- Q27 | COUNT / MIN / MAX + GROUP BY: workload of each staff member as
-- the issuer of allocations.
-- Expected: Priya Sundaram 7, Suresh Babu 6, Ramesh Kumar 5, Kavitha Ramesh 2.
SELECT ls.staff_id, ls.staff_name, ls.designation,
       COUNT(*)               AS allocations_issued,
       MIN(a.allocation_date) AS first_issue,
       MAX(a.allocation_date) AS latest_issue
FROM   lab_staff ls
JOIN   equipment_allocation a ON a.staff_id = ls.staff_id
GROUP  BY ls.staff_id, ls.staff_name, ls.designation
ORDER  BY allocations_issued DESC;
