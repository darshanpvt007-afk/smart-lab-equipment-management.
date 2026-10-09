# Review 2 Implementation Plan

**Project:** Smart Laboratory Equipment Inventory, Allocation and Maintenance Management System
**Review 2:** Database Design & SQL Implementation (deadline 12 October 2026)
**Target DBMS:** MySQL 8.0 (`utf8mb4`, InnoDB). Implemented and tested on MySQL 8.0.46.

## 1. Inspection summary (Phase 1)

| Item | Finding |
|---|---|
| Repository | Contained only a two-line `README.md`. No earlier SQL or application code to preserve. |
| Source documents | Both PDFs were read in full. *DATABASE SYSTEMS L3+L4.pdf* (3 pages) gives the review requirements. *DOC-20261005-WA0014.pdf* (26 pages) contains the Review 1 slides and report: entities, attributes, primary keys, relationships, cardinalities, ER diagram and explanation. |
| Database tools | MySQL was not installed in the working environment. With the student's approval, MySQL 8.0.46 was installed in the temporary cloud sandbox so that every script and test could actually be executed. No software was installed on the student's own machine. |

## 2. Extracted design (Review 1 → Review 2)

| Entity | Attributes (Review 1) | PK | Foreign keys needed |
|---|---|---|---|
| Supplier | Supplier_Name, Contact_Number, Email, Address | Supplier_ID | — |
| Purchase | Purchase_Date, Invoice_Number, Total_Amount, Purchase_Status | Purchase_ID | supplier_id |
| Equipment | Equipment_Name, Serial_Number, Condition, Availability_Status | Equipment_ID | category_id, lab_id, purchase_id |
| Equipment Category | Category_Name, Description | Category_ID | — |
| Lab | Lab_Name, Location, Capacity, Lab_Type | Lab_ID | — |
| Equipment Allocation | Allocation_Date, Expected_Return_Date, Allocation_Status | Allocation_ID | equipment_id, student_id, staff_id |
| Maintenance | Maintenance_Date, Maintenance_Type, Maintenance_Cost, Maintenance_Status, Remarks | Maintenance_ID | equipment_id, staff_id |
| Student | Student_Name, Register_Number, Department, Year, Email | Student_ID | — |
| Equipment Return | Return_Date, Return_Condition, Remarks | Return_ID | allocation_id (UNIQUE) |
| Lab Staff | Staff_Name, Designation, Department, Contact_Number, Email | Staff_ID | — |

Relationships: SUPPLIES, RESULTS_IN, CLASSIFIES, CONTAINS, IS_ALLOCATED, RECEIVES, ISSUES, UNDERGOES and PERFORMS are all 1:N. HAS_RETURN is 1:1.

The 10 foreign key columns are not in the Review 1 attribute lists. They are required to implement the approved relationships (DESIGN_DECISIONS D-03). Discrepancies noticed in the Review 1 material are listed in D-17. None required a design change.

## 3. Requirement → implementation → test mapping

| Official Review 2 requirement | SQL file | Documentation | Tests |
|---|---|---|---|
| Conversion of ER diagram into relational tables | `02_create_tables.sql` | RELATIONAL_SCHEMA.md, DESIGN_DECISIONS.md D-02–D-04, NORMALIZATION.md | TC01, TC02 |
| Primary keys and foreign keys | `02_create_tables.sql` | RELATIONAL_SCHEMA.md; DESIGN_DECISIONS D-03, D-05 | TC03, TC04, TC13, TC14 |
| Integrity constraints | `02_create_tables.sql`, `09_validation_queries.sql`, `11_transaction_procedures.sql` | DESIGN_DECISIONS D-07, D-08, D-10–D-13 | TC05, TC08–TC24, TC38–TC40, TC56–TC60 |
| Table creation | `01_create_database.sql`, `02_create_tables.sql` | README.md | TC01, TC62 |
| Sample data insertion | `03_insert_sample_data.sql` | DESIGN_DECISIONS D-18 | TC06, TC38 |
| SELECT | `04_basic_queries.sql` (and all others) | SQL_QUERY_CATALOG.md | TC07 |
| WHERE | `04_basic_queries.sql` | SQL_QUERY_CATALOG.md | TC07, TC25 |
| ORDER BY | `04_basic_queries.sql` | SQL_QUERY_CATALOG.md | TC07 |
| GROUP BY | `05_aggregate_queries.sql` | SQL_QUERY_CATALOG.md | TC26, TC27 |
| HAVING | `05_aggregate_queries.sql`, `07_subqueries.sql` | SQL_QUERY_CATALOG.md | TC29, TC34, TC35 |
| Aggregate functions | `05_aggregate_queries.sql` | SQL_QUERY_CATALOG.md | TC26–TC28 |
| JOIN | `06_join_queries.sql` | SQL_QUERY_CATALOG.md | TC30–TC32 |
| Subqueries | `07_subqueries.sql` | SQL_QUERY_CATALOG.md | TC32–TC35 |
| Views | `08_create_views.sql` | SQL_QUERY_CATALOG.md, RELATIONAL_SCHEMA.md | TC36, TC37 |
| Allocation conflict rule (Phase 5) | `02` (functional unique index), `09` (V08, V09), `11` | DESIGN_DECISIONS D-10 | TC23, TC40, TC42, TC53, TC54 |
| Availability consistency (Phase 5) | `02` (CHECK), `09` (V10–V12), `11` | DESIGN_DECISIONS D-08, D-11 | TC19, TC39, TC44, TC45, TC52 |
| Transactions & history (Phase 6) | `11_transaction_procedures.sql` | DESIGN_DECISIONS D-10, D-13, D-19 | TC41–TC52, TC56–TC60 |
| Reset & reproducibility | `10_reset_database.sql` | README.md, TROUBLESHOOTING.md | TC61–TC63 |
| Faculty demonstration | all | FACULTY_DEMONSTRATION.md | Demo SQL verified against a fresh build |

## 4. Work sequence (as carried out)

1. Read both PDFs and inspect the repository and tools.
2. Write `01`–`03`; run them on MySQL; confirm row counts and that no warnings appear.
3. Write `04`–`09` and `11`; run each file; compare the output with the expected values written in the query comments, and correct any comment that was wrong.
4. Write `tests/run_tests.sh`; run it; check that the helper functions really report failures (negative controls).
5. Write the documentation. Verify the demonstration SQL against a freshly built copy of the database.
6. Final consistency review across the ER design, schema, SQL, data and documentation; final test run (results in TEST_REPORT.md).

## 5. Scope boundary

| Review 2 (this delivery) | Deferred to Review 3 |
|---|---|
| Schema, constraints, sample data, all required SQL, views, validation, transaction procedures, tests, documentation | User interface, application database connectivity, CRUD screens, search forms, input validation in the UI, maintenance-workflow procedure, report generation, final report and presentation |
