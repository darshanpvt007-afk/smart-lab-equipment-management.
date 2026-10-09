# SQL Query Catalog

This catalog lists every numbered query in the `sql/` folder. Each query in the files carries the same ID in a comment (`-- Q01 | ...`).

All "Expected output" values were checked by running the scripts on MySQL 8.0.46 with the sample data. Date-dependent queries use the reference date 2026-10-10 (`@ref_date`; see DESIGN_DECISIONS D-09).

**Totals:** 55 queries (Q01–Q55), 16 validation checks (V01–V16), 4 views and 2 stored procedures.

## Coverage of the Review 2 requirements

| Requirement | Queries |
|---|---|
| SELECT | All queries (Q01 is the simplest) |
| WHERE | Q02–Q11, Q15, Q19, Q24, Q37, Q39, Q41–Q45, Q50, Q53–Q55 |
| ORDER BY | Q01–Q04, Q06–Q14 (Q12 two columns, Q13 DESC), and most others |
| GROUP BY | Q16–Q24, Q26–Q27, Q29, Q35, Q38, Q40, Q46–Q47, Q51 |
| HAVING | Q22, Q23, Q24, Q46, Q47 |
| Aggregate functions | COUNT Q16–Q18, Q21–Q27; SUM Q19, Q20, Q24, Q25; AVG Q20, Q25, Q39, Q45–Q46; MIN / MAX Q18, Q20, Q25, Q27, Q48 |
| JOIN | INNER Q16–Q19, Q28, Q30, Q31, Q33, Q36, Q37; LEFT Q29, Q32, Q34, Q35, Q38; 3+ tables Q30, Q31, Q33, Q36, Q37 |
| Subqueries | Scalar Q39, Q40; IN Q41; NOT IN Q42; EXISTS Q43; NOT EXISTS Q44; correlated Q43–Q45, Q48; derived table Q38, Q46; ALL Q49; aggregate benchmark Q39, Q46, Q47 |
| Views | 4 views; demonstrated by Q50–Q55 |
| LIMIT / LIKE / BETWEEN / IN / IS NULL | Q14 / Q04 / Q09 / Q08 / Q15 |

## sql/04_basic_queries.sql: SELECT, WHERE, ORDER BY

| ID | Concept | Purpose | Tables | Expected output |
|---|---|---|---|---|
| Q01 | SELECT, ORDER BY | List all equipment | equipment | 20 rows |
| Q02 | WHERE (=) | Equipment in lab 4 (Embedded Systems Lab) | equipment | 6 rows: equipment 3, 8, 9, 10, 11, 18 |
| Q03 | WHERE (=) | Equipment of category 2 (Multimeter) | equipment | 4 rows: equipment 4–7 |
| Q04 | WHERE + LIKE + OR | Search by name fragment or serial prefix | equipment | 7 rows: 3 oscilloscopes, 4 `NET-` items |
| Q05 | WHERE on UNIQUE column | Look up serial MCU-RPI-0010 | equipment | 1 row: Raspberry Pi 4 Kit, Allocated |
| Q06 | WHERE on status | Equipment that can be issued now | equipment | 11 rows |
| Q07 | WHERE + AND, ORDER BY DESC | CSE students in year ≥ 2 | student | 4 rows: Vikram (4), Aarav (3), Ishaan (2), Kabir (2) |
| Q08 | WHERE + IN | ECE and EEE students | student | 5 rows |
| Q09 | WHERE + BETWEEN | Allocations made in August 2026 | equipment_allocation | 7 rows: allocations 5–11 |
| Q10 | WHERE | Outstanding allocations | equipment_allocation | 6 rows: allocations 15–20 |
| Q11 | WHERE + date expression | Overdue allocations on the reference date | equipment_allocation | 3 rows: 15 (12 days), 16 (5), 17 (2) |
| Q12 | ORDER BY two columns | Equipment by name, then serial | equipment | 20 rows, alphabetical |
| Q13 | ORDER BY DESC | Purchases, newest first | purchase | 7 rows, OLE-2026-0301 first |
| Q14 | ORDER BY + LIMIT | Five most recent allocations | equipment_allocation | 5 rows: 20, 19, 18, 17, 16 |
| Q15 | IS NULL | Maintenance jobs without a cost yet | maintenance | 2 rows: maintenance 10, 11 (Scheduled) |

## sql/05_aggregate_queries.sql: aggregates, GROUP BY, HAVING

| ID | Concept | Purpose | Tables | Expected output |
|---|---|---|---|---|
| Q16 | COUNT, GROUP BY | Equipment per laboratory | lab, equipment | Embedded 6, Physics 5, Electronics 5, Networks 4 |
| Q17 | COUNT, GROUP BY | Equipment per category | equipment_category, equipment | 4, 4, 4, 3, 3, 2 |
| Q18 | COUNT, MIN, MAX, GROUP BY | Allocations per student with first / last date | student, equipment_allocation | 9 rows; Aarav 4 (top) |
| Q19 | SUM, COUNT, WHERE before GROUP BY | Received-purchase spending per supplier | supplier, purchase | Apex 208500.00, Orbit 72500.00, Zenith 68700.00, TechNova 39000.00 |
| Q20 | AVG, MIN, MAX, SUM, COUNT(*) vs COUNT(col) | Maintenance cost statistics per type | maintenance | Calibration avg 1400.00; Preventive 500.00; Repair 4816.67 |
| Q21 | COUNT, GROUP BY | Maintenance records by status | maintenance | Completed 7, In Progress 2, Scheduled 2 |
| Q22 | HAVING COUNT(*) > 2 | Students with more than 2 allocations | student, equipment_allocation | 4 rows: Aarav 4, Diya 3, Ishaan 3, Vikram 3 |
| Q23 | HAVING COUNT(*) > 4 | Labs holding more than 4 items | lab, equipment | 3 rows (Computer Networks Lab excluded) |
| Q24 | WHERE + GROUP BY + HAVING (two conditions) | Suppliers with > 1 non-cancelled purchase and total > 50,000 | supplier, purchase | 2 rows: Apex 208500.00, Orbit 118500.00 |
| Q25 | Aggregates without GROUP BY | One summary row over all purchases | purchase | 7 purchases, total 434700.00, avg 62100.00 |
| Q26 | COUNT, GROUP BY | Inventory by availability | equipment | Available 11, Allocated 6, Under Maintenance 2, Unavailable 1 |
| Q27 | COUNT, MIN, MAX, GROUP BY | Allocations issued per staff member | lab_staff, equipment_allocation | Priya 7, Suresh 6, Ramesh 5, Kavitha 2 |

## sql/06_join_queries.sql: JOINs

| ID | Concept | Purpose | Tables | Expected output |
|---|---|---|---|---|
| Q28 | INNER JOIN (2) | Purchases with their supplier | purchase, supplier | 7 rows |
| Q29 | LEFT JOIN + COUNT(col) | Every student's allocation count, including zero | student, equipment_allocation | 10 rows; Nisha Fernandes 0 |
| Q30 | INNER JOIN (3) | Equipment with category and lab | equipment, equipment_category, lab | 20 rows |
| Q31 | INNER JOIN (4) | Allocation register: student, equipment, issuer | equipment_allocation, student, equipment, lab_staff | 20 rows (one per allocation) |
| Q32 | LEFT JOIN on 1:1 | Allocations with return details | equipment_allocation, equipment, equipment_return | 20 rows; 15–20 "Not yet returned" |
| Q33 | INNER JOIN (3) | Maintenance history with staff | maintenance, equipment, lab_staff | 11 rows |
| Q34 | LEFT JOIN … IS NULL (anti-join) | Equipment never maintained | equipment, maintenance | 10 rows: 4, 6, 7, 8, 10, 11, 14, 15, 18, 20 |
| Q35 | LEFT JOIN + GROUP BY | Items received per purchase | purchase, equipment | 7 rows; purchase 7 has 0 |
| Q36 | INNER JOIN (5) | Equipment traceability to supplier | equipment, equipment_category, lab, purchase, supplier | 20 rows |
| Q37 | INNER JOIN + cross-table WHERE | Late returns | equipment_allocation, equipment_return, student, equipment | 2 rows: allocation 13 (2 days), 4 (1 day) |
| Q38 | LEFT JOIN to derived tables | Allocation and maintenance counts without row multiplication | equipment, equipment_allocation, maintenance | 20 rows; equipment 1 → 2, 2, 4250.00 |

## sql/07_subqueries.sql: subqueries

| ID | Concept | Purpose | Tables | Expected output |
|---|---|---|---|---|
| Q39 | Scalar subquery, comparison with AVG | Jobs costing more than the average (2238.89) | maintenance, equipment | 3 rows: maintenance 8, 5, 7 |
| Q40 | Scalar subquery in SELECT | Each category's % of inventory | equipment_category, equipment | 6 rows; Multimeter 20.0 % |
| Q41 | IN subquery | Students currently holding equipment | student, equipment_allocation | 6 rows: students 1, 2, 3, 5, 7, 9 |
| Q42 | NOT IN subquery | Students who never borrowed | student, equipment_allocation | 1 row: Nisha Fernandes |
| Q43 | EXISTS (correlated) | Equipment ever returned damaged | equipment, equipment_allocation, equipment_return | 2 rows: equipment 3, 9 |
| Q44 | NOT EXISTS (correlated) | Equipment with no maintenance history | equipment, maintenance | 10 rows (same as Q34) |
| Q45 | Correlated subquery | Jobs above the average of their own type | maintenance | 4 rows: maintenance 1, 2, 3, 8 |
| Q46 | Derived table + HAVING vs aggregate of aggregates | Equipment whose total maintenance cost exceeds the average per item (2518.75) | equipment, maintenance | 3 rows: equipment 3, 1, 19 |
| Q47 | HAVING vs scalar benchmark | Students above the average allocations per student (2.0) | student, equipment_allocation | 4 rows: Aarav, Diya, Ishaan, Vikram |
| Q48 | Correlated scalar subqueries in SELECT | Last issue date and last completed maintenance per item | equipment, equipment_allocation, maintenance | 20 rows; equipment 1 → 2026-10-01, 2026-09-02 |
| Q49 | `>= ALL` subquery | Largest purchase | purchase, supplier | 1 row: ASI-2025-0141, 105000.00 |

## sql/08_create_views.sql: views and queries over them

| View | Purpose | Rows |
|---|---|---|
| `vw_equipment_inventory` | Equipment + category + lab + purchase + supplier | 20 |
| `vw_outstanding_allocations` | Issued allocations with student, equipment, lab, issuer | 6 |
| `vw_maintenance_history` | Maintenance + equipment + lab + staff | 11 |
| `vw_allocation_history` | Allocations with their optional return and days late | 20 |

| ID | Concept | Purpose | View | Expected output |
|---|---|---|---|---|
| Q50 | View + WHERE | Available items in the Applied Physics Lab | vw_equipment_inventory | 4 rows |
| Q51 | View + GROUP BY + conditional SUM | Availability breakdown per lab | vw_equipment_inventory | 4 rows; Computer Networks 4 total, 2 available |
| Q52 | View | All outstanding items | vw_outstanding_allocations | 6 rows |
| Q53 | View + date filter | Overdue items on the reference date | vw_outstanding_allocations | 3 rows: 15, 16, 17 |
| Q54 | View + WHERE | Maintenance history of OSC-DS1-0001 | vw_maintenance_history | 2 rows |
| Q55 | View (contains LEFT JOIN) | Full history of student 24BCE1012 | vw_allocation_history | 4 rows; allocation 17 has no return |

## sql/09_validation_queries.sql: integrity checks

V01–V14 are violation checks. On correct data each returns **0 rows**, except V01, which returns one row of zeros. V15 and V16 are "to investigate" reports.

| ID | Checks | Rule enforced elsewhere by | Expected |
|---|---|---|---|
| V01 | Orphaned foreign keys (10 counts) | FOREIGN KEY constraints | all 0 |
| V02 | Duplicate register numbers | UNIQUE | 0 rows |
| V03 | Duplicate serial numbers | UNIQUE | 0 rows |
| V04 | Expected return before allocation date | CHECK | 0 rows |
| V05 | Dates after the reference date (except scheduled maintenance) | audit only (CHECK cannot use CURDATE) | 0 rows |
| V06 | Return before issue, or return exists but allocation still Issued | procedure | 0 rows |
| V07 | Allocation "Returned" without a return row | procedure | 0 rows |
| V08 | More than one active allocation per item | functional UNIQUE index | 0 rows |
| V09 | Overlapping loan periods in history | procedure + index | 0 rows |
| V10 | availability_status vs Issued allocations | procedures | 0 rows |
| V11 | availability_status vs In Progress maintenance | maintenance workflow | 0 rows |
| V12 | Damaged item available, or back in service without completed repair | CHECK + procedures | 0 rows |
| V13 | Negative cost, Completed without cost, maintenance before purchase | CHECK + audit | 0 rows |
| V14 | Missing associations, item from a non-received purchase, issued before purchase | NOT NULL + audit | 0 rows |
| V15 | Overdue outstanding allocations | report | 3 rows: 15, 16, 17 |
| V16 | Scheduled maintenance whose date has passed | report | 0 rows |

## sql/11_transaction_procedures.sql: stored procedures

| Procedure | Concept | Demonstrated by |
|---|---|---|
| `sp_allocate_equipment` | Transaction, `SELECT … FOR UPDATE`, `SIGNAL`, ROLLBACK on error | TC41–TC47, TC53 |
| `sp_return_equipment` | Multi-table atomic update, lock ordering | TC48–TC52 |

## sql/12_maintenance_procedures.sql: maintenance workflow (Review 3)

| Procedure | Concept | Demonstrated by |
|---|---|---|
| `sp_start_maintenance` | Transaction, row lock, business-rule refusal (no work on an issued item) | TC64–TC66, TA25, TA26, TB08 |
| `sp_complete_maintenance` | Multi-table atomic update; availability decided with CASE | TC67–TC70, TA25, TA27 |

## Queries run by the web application (Review 3)

`app/routes/reports.py` runs these queries, and the Reports page shows each one's SQL next to its live result.

| Report | Based on |
|---|---|
| Overdue allocations | Q53 |
| Equipment per laboratory | Q16 / Q51 |
| Expenditure per supplier | Q19 |
| Maintenance cost by type | Q20 |
| Students borrowing more than the average | Q47 |
| Equipment never maintained | Q44 |
| Late returns | Q37 |
| Jobs costing more than their type's average | Q45 |
