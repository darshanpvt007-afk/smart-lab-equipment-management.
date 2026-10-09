-- =====================================================================
-- File   : 04_basic_queries.sql
-- Purpose: SELECT, WHERE, ORDER BY, LIMIT, LIKE, BETWEEN, IN, IS NULL.
-- Queries: Q01 - Q15
-- Run    : mysql -u <user> -p -t < sql/04_basic_queries.sql
--
-- REFERENCE DATE
-- The sample data describes the labs on 2026-10-10. Date-dependent
-- queries use the session variable @ref_date so results are repeatable
-- on any day. For live use replace @ref_date with CURDATE().
-- =====================================================================

USE smart_lab_equipment_db;

SET @ref_date = DATE '2026-10-10';

-- Q01 | SELECT: list every equipment item with its stored status.
-- Expected: 20 rows.
SELECT equipment_id, equipment_name, serial_number,
       equipment_condition, availability_status
FROM   equipment
ORDER  BY equipment_id;

-- Q02 | WHERE: equipment kept in one laboratory (lab_id 4 = Embedded Systems Lab).
-- Expected: 6 rows (equipment 3, 8, 9, 10, 11, 18).
SELECT equipment_id, equipment_name, serial_number, availability_status
FROM   equipment
WHERE  lab_id = 4
ORDER  BY equipment_name;

-- Q03 | WHERE: equipment of one category (category_id 2 = Multimeter).
-- Expected: 4 rows (equipment 4, 5, 6, 7).
SELECT equipment_id, equipment_name, serial_number, lab_id
FROM   equipment
WHERE  category_id = 2
ORDER  BY equipment_id;

-- Q04 | WHERE + LIKE: search by part of the name OR a serial-number prefix.
-- '%' matches any sequence of characters.
-- Expected: 7 rows (3 oscilloscopes + 4 items whose serial starts with NET-).
SELECT equipment_id, equipment_name, serial_number
FROM   equipment
WHERE  equipment_name LIKE '%Oscilloscope%'
   OR  serial_number  LIKE 'NET-%'
ORDER  BY serial_number;

-- Q05 | WHERE with equality on a UNIQUE column: look up one serial number.
-- Expected: exactly 1 row (Raspberry Pi 4 Kit).
SELECT equipment_id, equipment_name, equipment_condition, availability_status
FROM   equipment
WHERE  serial_number = 'MCU-RPI-0010';

-- Q06 | WHERE on availability: items that can be issued right now.
-- Expected: 11 rows.
SELECT equipment_id, equipment_name, serial_number, equipment_condition
FROM   equipment
WHERE  availability_status = 'Available'
ORDER  BY equipment_name, serial_number;

-- Q07 | WHERE with AND: CSE students in year 2 or above, senior first.
-- Expected: 4 rows (Vikram yr 4, Aarav yr 3, Ishaan yr 2, Kabir yr 2).
-- Sneha Pillai (CSE, year 1) is excluded by the second condition.
SELECT student_id, register_number, student_name, department, year_of_study
FROM   student
WHERE  department = 'CSE'
  AND  year_of_study >= 2
ORDER  BY year_of_study DESC, student_name;

-- Q08 | WHERE with IN: students of the ECE and EEE departments.
-- Expected: 5 rows.
SELECT register_number, student_name, department, year_of_study
FROM   student
WHERE  department IN ('ECE', 'EEE')
ORDER  BY department, student_name;

-- Q09 | WHERE with BETWEEN: allocations made during August 2026.
-- BETWEEN is inclusive of both end dates.
-- Expected: 7 rows (allocations 5 - 11).
SELECT allocation_id, equipment_id, student_id, allocation_date, allocation_status
FROM   equipment_allocation
WHERE  allocation_date BETWEEN '2026-08-01' AND '2026-08-31'
ORDER  BY allocation_date;

-- Q10 | Outstanding allocations: equipment that is still with a student.
-- Expected: 6 rows (allocations 15 - 20).
SELECT allocation_id, equipment_id, student_id, allocation_date, expected_return_date
FROM   equipment_allocation
WHERE  allocation_status = 'Issued'
ORDER  BY expected_return_date;

-- Q11 | Overdue allocations: still issued AND the expected return date
-- is before the reference date. DATEDIFF gives the days overdue.
-- Expected on 2026-10-10: 3 rows (allocations 15, 16, 17 -> 12, 5, 2 days).
-- Live version: replace @ref_date with CURDATE().
SELECT allocation_id, equipment_id, student_id, expected_return_date,
       DATEDIFF(@ref_date, expected_return_date) AS days_overdue
FROM   equipment_allocation
WHERE  allocation_status = 'Issued'
  AND  expected_return_date < @ref_date
ORDER  BY days_overdue DESC;

-- Q12 | ORDER BY on two columns: equipment sorted by name, then serial.
-- Expected: 20 rows, alphabetical.
SELECT equipment_name, serial_number, availability_status
FROM   equipment
ORDER  BY equipment_name ASC, serial_number ASC;

-- Q13 | ORDER BY date DESC: purchase records, newest first.
-- Expected: 7 rows, starting with OLE-2026-0301 (2026-09-28, Ordered).
SELECT purchase_id, purchase_date, invoice_number, total_amount, purchase_status
FROM   purchase
ORDER  BY purchase_date DESC;

-- Q14 | ORDER BY + LIMIT: the five most recent allocations.
-- Expected: 5 rows (allocations 20, 19, 18, 17, 16).
SELECT allocation_id, equipment_id, student_id, allocation_date
FROM   equipment_allocation
ORDER  BY allocation_date DESC, allocation_id DESC
LIMIT  5;

-- Q15 | WHERE ... IS NULL: maintenance jobs whose cost is not known yet.
-- "= NULL" never matches; IS NULL must be used.
-- Expected: 2 rows (maintenance 10 and 11, both Scheduled).
SELECT maintenance_id, equipment_id, maintenance_date, maintenance_type, maintenance_status
FROM   maintenance
WHERE  maintenance_cost IS NULL
ORDER  BY maintenance_date;
