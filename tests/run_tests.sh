#!/usr/bin/env bash
# =====================================================================
# Automated test runner for the Review 2 database.
#
# SAFETY: the tests never touch smart_lab_equipment_db. Every SQL file is
# copied with the database name replaced by smart_lab_equipment_test and
# all tests run against that separate database, which this script
# creates and drops itself (set KEEP_TEST_DB=1 to keep it afterwards).
#
# Usage (from the project root):
#     bash tests/run_tests.sh
# Connection: by default the plain `mysql` client is used, which reads
# ~/.my.cnf or the socket login of the current OS user. To use a saved
# login path instead (recommended, no password on the command line):
#     mysql_config_editor set --login-path=smartlab --user=root --password
#     MYSQL_CMD="mysql --login-path=smartlab" bash tests/run_tests.sh
#
# Exit status: 0 if every test passes, 1 otherwise.
# =====================================================================
set -u

MYSQL_CMD=${MYSQL_CMD:-mysql}
DEV_DB=smart_lab_equipment_db
TEST_DB=smart_lab_equipment_test
ROOT=$(cd "$(dirname "$0")/.." && pwd)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

PASS=0
FAIL=0

# ---------- helpers ---------------------------------------------------
# Copy an SQL file, retargeting it at the test database.
testcopy() {
    sed "s/${DEV_DB}/${TEST_DB}/g" "$ROOT/sql/$1" > "$WORK/$1"
    printf '%s' "$WORK/$1"
}

# Run SQL text against the test DB; print rows tab-separated, no headers.
q() {
    $MYSQL_CMD -N -B "$TEST_DB" -e "$1" 2>&1
}

report() {   # id, description, PASS|FAIL, detail
    if [ "$3" = PASS ]; then
        PASS=$((PASS + 1)); printf 'PASS  %-5s %s\n' "$1" "$2"
    else
        FAIL=$((FAIL + 1)); printf 'FAIL  %-5s %s\n      %s\n' "$1" "$2" "$4"
    fi
}

# expect_value ID "description" "SQL returning one value" "expected"
expect_value() {
    local actual
    actual=$(q "$3")
    if [ "$actual" = "$4" ]; then
        report "$1" "$2" PASS ""
    else
        report "$1" "$2" FAIL "expected [$4] got [$actual]"
    fi
}

# expect_error ID "description" "SQL" error_code
expect_error() {
    local out
    out=$(q "$3")
    if printf '%s' "$out" | grep -q "^ERROR $4 "; then
        report "$1" "$2" PASS ""
    else
        report "$1" "$2" FAIL "expected ERROR $4 got [$out]"
    fi
}

# run_script ID "description" file... : must finish with no ERROR/Warning
run_scripts() {
    local id=$1 desc=$2 out f all=""
    shift 2
    for f in "$@"; do
        out=$($MYSQL_CMD --show-warnings < "$(testcopy "$f")" 2>&1)
        if [ $? -ne 0 ] || printf '%s' "$out" | grep -qE '^(ERROR|Warning)'; then
            all="$all [$f: $(printf '%s' "$out" | grep -E '^(ERROR|Warning)' | head -3)]"
        fi
    done
    if [ -z "$all" ]; then report "$id" "$desc" PASS ""; else report "$id" "$desc" FAIL "$all"; fi
}

if ! $MYSQL_CMD -e "SELECT 1" >/dev/null 2>&1; then
    echo "Cannot connect to MySQL with: $MYSQL_CMD"; exit 1
fi

echo "MySQL version : $($MYSQL_CMD -N -B -e 'SELECT VERSION()')"
echo "Test database : $TEST_DB (the development database $DEV_DB is not used)"
echo "---------------------------------------------------------------------"

$MYSQL_CMD -e "DROP DATABASE IF EXISTS ${TEST_DB}"

# ---------- 1. build & schema ----------------------------------------
run_scripts TC01 "Clean build: 01, 02, 03, 08, 11, 12 run without errors or warnings" \
    01_create_database.sql 02_create_tables.sql 03_insert_sample_data.sql \
    08_create_views.sql 11_transaction_procedures.sql 12_maintenance_procedures.sql

expect_value TC02 "All 10 base tables exist" \
 "SELECT GROUP_CONCAT(TABLE_NAME ORDER BY TABLE_NAME) FROM information_schema.TABLES
  WHERE TABLE_SCHEMA='${TEST_DB}' AND TABLE_TYPE='BASE TABLE'" \
 "equipment,equipment_allocation,equipment_category,equipment_return,lab,lab_staff,maintenance,purchase,student,supplier"

expect_value TC03 "Every table has a PRIMARY KEY" \
 "SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
  WHERE TABLE_SCHEMA='${TEST_DB}' AND CONSTRAINT_TYPE='PRIMARY KEY'" "10"

expect_value TC04 "All 10 foreign keys declared with the right parent tables" \
 "SELECT GROUP_CONCAT(CONCAT(TABLE_NAME,'.',COLUMN_NAME,'->',REFERENCED_TABLE_NAME) ORDER BY TABLE_NAME, COLUMN_NAME)
  FROM information_schema.KEY_COLUMN_USAGE
  WHERE TABLE_SCHEMA='${TEST_DB}' AND REFERENCED_TABLE_NAME IS NOT NULL" \
 "equipment.category_id->equipment_category,equipment.lab_id->lab,equipment.purchase_id->purchase,equipment_allocation.equipment_id->equipment,equipment_allocation.staff_id->lab_staff,equipment_allocation.student_id->student,equipment_return.allocation_id->equipment_allocation,maintenance.equipment_id->equipment,maintenance.staff_id->lab_staff,purchase.supplier_id->supplier"

expect_value TC05 "Foreign keys use ON DELETE RESTRICT (history cannot be cascaded away)" \
 "SELECT GROUP_CONCAT(DISTINCT DELETE_RULE) FROM information_schema.REFERENTIAL_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA='${TEST_DB}'" "RESTRICT"

expect_value TC06 "Sample data row counts (lab..maintenance)" \
 "SELECT CONCAT_WS(',',(SELECT COUNT(*) FROM lab),(SELECT COUNT(*) FROM equipment_category),
   (SELECT COUNT(*) FROM supplier),(SELECT COUNT(*) FROM purchase),(SELECT COUNT(*) FROM student),
   (SELECT COUNT(*) FROM lab_staff),(SELECT COUNT(*) FROM equipment),(SELECT COUNT(*) FROM equipment_allocation),
   (SELECT COUNT(*) FROM equipment_return),(SELECT COUNT(*) FROM maintenance))" \
 "4,6,4,7,10,4,20,20,14,11"

run_scripts TC07 "Query scripts 04, 05, 06, 07, 09 run without errors or warnings" \
    04_basic_queries.sql 05_aggregate_queries.sql 06_join_queries.sql \
    07_subqueries.sql 09_validation_queries.sql

# ---------- 2. constraints -------------------------------------------
expect_value TC08 "Valid INSERT of a new student succeeds (rolled back afterwards)" \
 "START TRANSACTION;
  INSERT INTO student (student_name, register_number, department, year_of_study, email)
  VALUES ('Test Student','26BCE1999','CSE',1,'test.student@students.example.edu');
  SELECT COUNT(*) FROM student; ROLLBACK;" "11"

expect_error TC09 "Duplicate student register_number rejected (UNIQUE)" \
 "INSERT INTO student (student_name, register_number, department, year_of_study, email)
  VALUES ('Duplicate','24BCE1012','CSE',3,'dup@students.example.edu')" 1062

expect_error TC10 "Duplicate equipment serial_number rejected (UNIQUE)" \
 "INSERT INTO equipment (equipment_name, serial_number, category_id, lab_id, purchase_id)
  VALUES ('Copy','OSC-DS1-0001',1,2,1)" 1062

expect_error TC11 "Duplicate invoice number from the SAME supplier rejected" \
 "INSERT INTO purchase (supplier_id, purchase_date, invoice_number, total_amount)
  VALUES (1,'2026-10-01','ASI-2025-0141',1000.00)" 1062

expect_value TC12 "Same invoice number from a DIFFERENT supplier is allowed (rolled back)" \
 "START TRANSACTION;
  INSERT INTO purchase (supplier_id, purchase_date, invoice_number, total_amount)
  VALUES (2,'2026-10-01','ASI-2025-0141',1000.00);
  SELECT COUNT(*) FROM purchase WHERE invoice_number='ASI-2025-0141'; ROLLBACK;" "2"

expect_error TC13 "Equipment with a non-existent lab rejected (FOREIGN KEY)" \
 "INSERT INTO equipment (equipment_name, serial_number, category_id, lab_id, purchase_id)
  VALUES ('Orphan','TST-0001',1,99,1)" 1452

expect_error TC14 "Allocation for a non-existent student rejected (FOREIGN KEY)" \
 "INSERT INTO equipment_allocation (equipment_id, student_id, staff_id, allocation_date, expected_return_date, allocation_status)
  VALUES (2,999,1,'2026-10-10','2026-10-17','Returned')" 1452

expect_error TC15 "NULL lab_id rejected (NOT NULL)" \
 "INSERT INTO equipment (equipment_name, serial_number, category_id, lab_id, purchase_id)
  VALUES ('No lab','TST-0002',1,NULL,1)" 1048

expect_error TC16 "year_of_study = 7 rejected (CHECK)" \
 "INSERT INTO student (student_name, register_number, department, year_of_study, email)
  VALUES ('Bad Year','26BCE1998','CSE',7,'bad.year@students.example.edu')" 3819

expect_error TC17 "Negative purchase amount rejected (CHECK)" \
 "INSERT INTO purchase (supplier_id, purchase_date, invoice_number, total_amount)
  VALUES (1,'2026-10-01','NEG-0001',-500.00)" 3819

expect_error TC18 "Expected return date before allocation date rejected (CHECK)" \
 "INSERT INTO equipment_allocation (equipment_id, student_id, staff_id, allocation_date, expected_return_date, allocation_status)
  VALUES (2,10,1,'2026-10-10','2026-10-01','Returned')" 3819

expect_error TC19 "Damaged equipment cannot be marked Available (CHECK)" \
 "UPDATE equipment SET availability_status='Available' WHERE equipment_id=9" 3819

expect_error TC20 "Invalid allocation_status 'Lost' rejected (CHECK)" \
 "UPDATE equipment_allocation SET allocation_status='Lost' WHERE allocation_id=1" 3819

expect_error TC21 "Completed maintenance without a cost rejected (CHECK)" \
 "INSERT INTO maintenance (equipment_id, staff_id, maintenance_date, maintenance_type, maintenance_status)
  VALUES (2,1,'2026-10-01','Preventive','Completed')" 3819

expect_error TC22 "Second return for the same allocation rejected (1:1, UNIQUE)" \
 "INSERT INTO equipment_return (allocation_id, return_date, return_condition)
  VALUES (1,'2026-07-13','Good')" 1062

expect_error TC23 "Second ACTIVE allocation of the same equipment rejected (functional UNIQUE index)" \
 "INSERT INTO equipment_allocation (equipment_id, student_id, staff_id, allocation_date, expected_return_date, allocation_status)
  VALUES (1,10,1,'2026-10-10','2026-10-17','Issued')" 1062

expect_value TC24 "Many RETURNED allocations of the same equipment are still allowed (rolled back)" \
 "START TRANSACTION;
  INSERT INTO equipment_allocation (equipment_id, student_id, staff_id, allocation_date, expected_return_date, allocation_status)
  VALUES (2,10,1,'2026-05-01','2026-05-08','Returned');
  SELECT COUNT(*) FROM equipment_allocation WHERE equipment_id=2; ROLLBACK;" "2"

# ---------- 3. query results -----------------------------------------
expect_value TC25 "Unreturned allocations (LEFT JOIN, no return row)" \
 "SELECT GROUP_CONCAT(a.allocation_id ORDER BY a.allocation_id) FROM equipment_allocation a
  LEFT JOIN equipment_return r ON r.allocation_id=a.allocation_id WHERE r.return_id IS NULL" \
 "15,16,17,18,19,20"

expect_value TC26 "Aggregation: equipment count per lab (Q16)" \
 "SELECT GROUP_CONCAT(CONCAT(lab_name,':',n) ORDER BY lab_name) FROM
  (SELECT l.lab_name, COUNT(*) n FROM lab l JOIN equipment e ON e.lab_id=l.lab_id GROUP BY l.lab_id, l.lab_name) t" \
 "Applied Physics Lab:5,Computer Networks Lab:4,Electronics and Circuits Lab:5,Embedded Systems Lab:6"

expect_value TC27 "Aggregation: received purchase expenditure per supplier (Q19)" \
 "SELECT GROUP_CONCAT(CONCAT(supplier_id,':',t) ORDER BY supplier_id) FROM
  (SELECT supplier_id, SUM(total_amount) t FROM purchase WHERE purchase_status='Received' GROUP BY supplier_id) x" \
 "1:208500.00,2:39000.00,3:72500.00,4:68700.00"

expect_value TC28 "Aggregation: average cost per maintenance type, NULLs ignored (Q20)" \
 "SELECT GROUP_CONCAT(CONCAT(maintenance_type,':',a) ORDER BY maintenance_type) FROM
  (SELECT maintenance_type, ROUND(AVG(maintenance_cost),2) a FROM maintenance GROUP BY maintenance_type) x" \
 "Calibration:1400.00,Preventive:500.00,Repair:4816.67"

expect_value TC29 "HAVING: students with more than 2 allocations (Q22)" \
 "SELECT GROUP_CONCAT(student_id ORDER BY student_id) FROM
  (SELECT student_id FROM equipment_allocation GROUP BY student_id HAVING COUNT(*) > 2) x" "1,2,7,9"

expect_value TC30 "JOIN: 4-table allocation register returns one row per allocation (Q31)" \
 "SELECT COUNT(*) FROM equipment_allocation a JOIN student s ON s.student_id=a.student_id
  JOIN equipment e ON e.equipment_id=a.equipment_id JOIN lab_staff ls ON ls.staff_id=a.staff_id" "20"

expect_value TC31 "JOIN: pre-aggregated counts avoid row multiplication for equipment 1 (Q38)" \
 "SELECT CONCAT_WS(',',al.c,mt.c,mt.s) FROM equipment e
  JOIN (SELECT equipment_id, COUNT(*) c FROM equipment_allocation GROUP BY equipment_id) al ON al.equipment_id=e.equipment_id
  JOIN (SELECT equipment_id, COUNT(*) c, SUM(maintenance_cost) s FROM maintenance GROUP BY equipment_id) mt ON mt.equipment_id=e.equipment_id
  WHERE e.equipment_id=1" "2,2,4250.00"

expect_value TC32 "Equipment without maintenance: NOT EXISTS (Q44) = LEFT JOIN anti-join (Q34)" \
 "SELECT CONCAT((SELECT GROUP_CONCAT(e.equipment_id ORDER BY e.equipment_id) FROM equipment e
          WHERE NOT EXISTS (SELECT 1 FROM maintenance m WHERE m.equipment_id=e.equipment_id)), ' | ',
         (SELECT GROUP_CONCAT(e.equipment_id ORDER BY e.equipment_id) FROM equipment e
          LEFT JOIN maintenance m ON m.equipment_id=e.equipment_id WHERE m.maintenance_id IS NULL))" \
 "4,6,7,8,10,11,14,15,18,20 | 4,6,7,8,10,11,14,15,18,20"

expect_value TC33 "Correlated subquery: jobs above their type's average cost (Q45)" \
 "SELECT GROUP_CONCAT(m.maintenance_id ORDER BY m.maintenance_id) FROM maintenance m
  WHERE m.maintenance_cost > (SELECT AVG(m2.maintenance_cost) FROM maintenance m2 WHERE m2.maintenance_type=m.maintenance_type)" \
 "1,2,3,8"

expect_value TC34 "Subquery: equipment with total maintenance cost above average (Q46)" \
 "SELECT GROUP_CONCAT(equipment_id ORDER BY equipment_id) FROM
  (SELECT equipment_id FROM maintenance GROUP BY equipment_id
   HAVING SUM(maintenance_cost) > (SELECT AVG(t) FROM (SELECT SUM(maintenance_cost) t FROM maintenance GROUP BY equipment_id) p)) x" \
 "1,3,19"

expect_value TC35 "Subquery: students above the average allocation benchmark (Q47)" \
 "SELECT GROUP_CONCAT(student_id ORDER BY student_id) FROM
  (SELECT student_id FROM equipment_allocation GROUP BY student_id
   HAVING COUNT(*) > (SELECT COUNT(*) FROM equipment_allocation)/(SELECT COUNT(*) FROM student)) x" "1,2,7,9"

expect_value TC36 "Views exist and return the expected row counts" \
 "SELECT CONCAT_WS(',',(SELECT COUNT(*) FROM vw_equipment_inventory),(SELECT COUNT(*) FROM vw_outstanding_allocations),
   (SELECT COUNT(*) FROM vw_maintenance_history),(SELECT COUNT(*) FROM vw_allocation_history))" "20,6,11,20"

expect_value TC37 "View: overdue allocations on 2026-10-10 (Q53)" \
 "SELECT GROUP_CONCAT(allocation_id ORDER BY allocation_id) FROM vw_outstanding_allocations
  WHERE expected_return_date < '2026-10-10'" "15,16,17"

# ---------- 4. validation queries ------------------------------------
V_EXPECTED=$(printf '0\t0\t0\t0\t0\t0\t0\t0\t0\t0\n15\tVikram Joshi\tvikram.joshi@students.example.edu\tNET-SW24-0012\t2026-09-28\t12\n16\tRohan Kulkarni\trohan.kulkarni@students.example.edu\tDMM-17B-0004\t2026-10-05\t5\n17\tAarav Menon\taarav.menon@students.example.edu\tOSC-DS1-0001\t2026-10-08\t2')
check_validation() {   # id description
    local out
    out=$($MYSQL_CMD -N -B < "$(testcopy 09_validation_queries.sql)" 2>&1)
    if [ "$out" = "$V_EXPECTED" ]; then report "$1" "$2" PASS ""
    else report "$1" "$2" FAIL "unexpected output: $(printf '%s' "$out" | head -8 | tr '\n' ';')"; fi
}
check_validation TC38 "Validation checks V01-V14, V16 find no violations; V15 lists the 3 overdue loans"

V10_SQL="SELECT e.equipment_id FROM equipment e LEFT JOIN equipment_allocation a
  ON a.equipment_id=e.equipment_id AND a.allocation_status='Issued'
  GROUP BY e.equipment_id, e.availability_status
  HAVING (e.availability_status='Allocated' AND COUNT(a.allocation_id)=0)
      OR (e.availability_status<>'Allocated' AND COUNT(a.allocation_id)>0)"
expect_value TC39 "Validation V10 detects availability drift (equipment 1 wrongly set Available)" \
 "START TRANSACTION; UPDATE equipment SET availability_status='Available' WHERE equipment_id=1;
  ${V10_SQL}; ROLLBACK;" "1"

expect_value TC40 "Validation V09 detects overlapping loan periods of one equipment item" \
 "START TRANSACTION;
  INSERT INTO equipment_allocation (allocation_id, equipment_id, student_id, staff_id, allocation_date, expected_return_date, allocation_status)
  VALUES (900,2,10,1,'2026-07-08','2026-07-09','Returned');
  INSERT INTO equipment_return (allocation_id, return_date, return_condition) VALUES (900,'2026-07-09','Good');
  SELECT CONCAT(a1.allocation_id,'/',a2.allocation_id) FROM equipment_allocation a1
  LEFT JOIN equipment_return r1 ON r1.allocation_id=a1.allocation_id
  JOIN equipment_allocation a2 ON a2.equipment_id=a1.equipment_id AND a2.allocation_id<>a1.allocation_id
       AND a2.allocation_date>=a1.allocation_date
  WHERE r1.return_id IS NULL OR a2.allocation_date < r1.return_date; ROLLBACK;" "1/900"

# ---------- 5. transactions (stored procedures) ----------------------
expect_value TC41 "sp_allocate_equipment issues an Available item and marks it Allocated" \
 "CALL sp_allocate_equipment(15,10,1,'2026-10-10','2026-10-17',@id);
  SELECT CONCAT_WS(',',a.allocation_status,e.availability_status,a.student_id)
  FROM equipment_allocation a JOIN equipment e ON e.equipment_id=a.equipment_id WHERE a.allocation_id=@id" \
 "Issued,Allocated,10"

expect_error TC42 "sp_allocate_equipment refuses an item that is already Allocated" \
 "CALL sp_allocate_equipment(15,3,1,'2026-10-10','2026-10-17',@id)" 1644

expect_value TC43 "...and the refused call left exactly one active allocation for that item" \
 "SELECT COUNT(*) FROM equipment_allocation WHERE equipment_id=15 AND allocation_status='Issued'" "1"

expect_error TC44 "sp_allocate_equipment refuses an item Under Maintenance (equipment 3)" \
 "CALL sp_allocate_equipment(3,10,1,'2026-10-10','2026-10-17',@id)" 1644

expect_error TC45 "sp_allocate_equipment refuses a Damaged/Unavailable item (equipment 9)" \
 "CALL sp_allocate_equipment(9,10,1,'2026-10-10','2026-10-17',@id)" 1644

expect_error TC46 "sp_allocate_equipment with an unknown student fails with the FK error..." \
 "CALL sp_allocate_equipment(2,999,1,'2026-10-10','2026-10-17',@id)" 1452

expect_value TC47 "...and is fully rolled back (equipment 2 still Available, no new allocation)" \
 "SELECT CONCAT_WS(',',(SELECT availability_status FROM equipment WHERE equipment_id=2),
   (SELECT COUNT(*) FROM equipment_allocation WHERE equipment_id=2))" "Available,1"

expect_value TC48 "sp_return_equipment records the return and makes the item Available" \
 "SET @id=(SELECT allocation_id FROM equipment_allocation WHERE equipment_id=15 AND allocation_status='Issued');
  CALL sp_return_equipment(@id,'2026-10-10','Good','Returned complete');
  SELECT CONCAT_WS(',',a.allocation_status,e.availability_status,e.equipment_condition,r.return_date)
  FROM equipment_allocation a JOIN equipment e ON e.equipment_id=a.equipment_id
  JOIN equipment_return r ON r.allocation_id=a.allocation_id WHERE a.allocation_id=@id" \
 "Returned,Available,Good,2026-10-10"

expect_error TC49 "sp_return_equipment refuses to return the same allocation twice" \
 "CALL sp_return_equipment(1,'2026-10-12','Good',NULL)" 1644

expect_error TC50 "sp_return_equipment refuses a return dated before the allocation" \
 "CALL sp_return_equipment(18,'2026-10-01','Good',NULL)" 1644

expect_value TC51 "...and allocation 18 is unchanged (still Issued, no return row)" \
 "SELECT CONCAT_WS(',',(SELECT allocation_status FROM equipment_allocation WHERE allocation_id=18),
   (SELECT COUNT(*) FROM equipment_return WHERE allocation_id=18))" "Issued,0"

expect_value TC52 "Returning an item Damaged makes it Unavailable with condition Damaged" \
 "CALL sp_return_equipment(19,'2026-10-10','Damaged','Screen cracked');
  SELECT CONCAT_WS(',',availability_status,equipment_condition) FROM equipment WHERE equipment_id=10" \
 "Unavailable,Damaged"

# ---------- 6. concurrency -------------------------------------------
# TC53: two sessions call sp_allocate_equipment for the SAME item at the
# same moment. A third session holds the equipment row lock for 2 s so
# both calls are guaranteed to overlap and wait.
$MYSQL_CMD -N -B "$TEST_DB" -e "START TRANSACTION; SELECT equipment_id FROM equipment WHERE equipment_id=2 FOR UPDATE; DO SLEEP(2); COMMIT;" >/dev/null 2>&1 &
HOLDER=$!
sleep 0.5
$MYSQL_CMD -N -B "$TEST_DB" -e "CALL sp_allocate_equipment(2,4,1,'2026-10-10','2026-10-17',@a); SELECT 'OK'" > "$WORK/s1.out" 2>&1 &
S1=$!
$MYSQL_CMD -N -B "$TEST_DB" -e "CALL sp_allocate_equipment(2,8,2,'2026-10-10','2026-10-17',@b); SELECT 'OK'" > "$WORK/s2.out" 2>&1 &
S2=$!
wait $HOLDER $S1 $S2
OK_COUNT=$(cat "$WORK/s1.out" "$WORK/s2.out" | grep -c '^OK$')
REFUSED=$(cat "$WORK/s1.out" "$WORK/s2.out" | grep -c '^ERROR 1644')
ACTIVE=$(q "SELECT COUNT(*) FROM equipment_allocation WHERE equipment_id=2 AND allocation_status='Issued'")
if [ "$OK_COUNT" = 1 ] && [ "$REFUSED" = 1 ] && [ "$ACTIVE" = 1 ]; then
    report TC53 "Concurrent sp_allocate_equipment on one item: exactly one succeeds" PASS ""
else
    report TC53 "Concurrent sp_allocate_equipment on one item: exactly one succeeds" FAIL \
        "ok=$OK_COUNT refused=$REFUSED active=$ACTIVE s1=[$(cat "$WORK/s1.out")] s2=[$(cat "$WORK/s2.out")]"
fi

# TC54: bypass the procedures entirely. Session A inserts an 'Issued'
# allocation for equipment 5 and keeps its transaction open for 2 s;
# session B inserts a conflicting one meanwhile. The unique index makes
# B wait for A and then fail with a duplicate-key error.
$MYSQL_CMD -N -B "$TEST_DB" -e "START TRANSACTION;
  INSERT INTO equipment_allocation (allocation_id, equipment_id, student_id, staff_id, allocation_date, expected_return_date, allocation_status)
  VALUES (950,5,6,1,'2026-10-10','2026-10-17','Issued'); DO SLEEP(2); COMMIT; SELECT 'OK'" > "$WORK/a.out" 2>&1 &
A=$!
sleep 0.5
$MYSQL_CMD -N -B "$TEST_DB" -e "INSERT INTO equipment_allocation (equipment_id, student_id, staff_id, allocation_date, expected_return_date, allocation_status)
  VALUES (5,7,2,'2026-10-10','2026-10-17','Issued'); SELECT 'OK'" > "$WORK/b.out" 2>&1 &
B=$!
wait $A $B
if grep -q '^OK$' "$WORK/a.out" && grep -q '^ERROR 1062' "$WORK/b.out"; then
    report TC54 "Concurrent direct INSERTs of active allocations: second is rejected (1062)" PASS ""
else
    report TC54 "Concurrent direct INSERTs of active allocations: second is rejected (1062)" FAIL \
        "a=[$(cat "$WORK/a.out")] b=[$(cat "$WORK/b.out")]"
fi
# Remove TC54's deliberately unmanaged row so the data is consistent again.
q "DELETE FROM equipment_allocation WHERE allocation_id=950" >/dev/null

# Expected V15 output after the procedure tests is unchanged (allocations
# 15-17 are still the only overdue ones) and nothing else is violated.
check_validation TC55 "After all procedure calls, validation still finds no violations"

# ---------- 7. history preservation ----------------------------------
expect_error TC56 "Deleting a student with allocation history is blocked (RESTRICT)" \
 "DELETE FROM student WHERE student_id=1" 1451
expect_error TC57 "Deleting equipment with allocation/maintenance history is blocked" \
 "DELETE FROM equipment WHERE equipment_id=1" 1451
expect_error TC58 "Deleting an allocation that has a return record is blocked" \
 "DELETE FROM equipment_allocation WHERE allocation_id=1" 1451
expect_error TC59 "Deleting a supplier with purchases is blocked" \
 "DELETE FROM supplier WHERE supplier_id=1" 1451
expect_value TC60 "All 14 original returns and 11 maintenance records still present" \
 "SELECT CONCAT_WS(',',(SELECT COUNT(*) FROM equipment_return WHERE return_id<=14),(SELECT COUNT(*) FROM maintenance))" "14,11"

# ---------- 8. reset & reproducibility -------------------------------
$MYSQL_CMD < "$(testcopy 10_reset_database.sql)" >/dev/null 2>&1
LEFT_OVER=$($MYSQL_CMD -N -B -e "SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME='${TEST_DB}'" 2>&1)
if [ "$LEFT_OVER" = 0 ]; then
    report TC61 "Reset script (run on the TEST database only) drops the database" PASS ""
else
    report TC61 "Reset script (run on the TEST database only) drops the database" FAIL "schemas found: $LEFT_OVER"
fi

run_scripts TC62 "Rebuild after reset succeeds (reproducible from a clean server)" \
    01_create_database.sql 02_create_tables.sql 03_insert_sample_data.sql \
    08_create_views.sql 11_transaction_procedures.sql 12_maintenance_procedures.sql
check_validation TC63 "Rebuilt database passes validation again"

# ---------- 9. maintenance workflow (Review 3, file 12) --------------
expect_value TC64 "sp_start_maintenance starts a Scheduled job and sets the item Under Maintenance" \
 "CALL sp_start_maintenance(10,'2026-10-10');
  SELECT CONCAT_WS(',',m.maintenance_status,m.maintenance_date,e.availability_status)
  FROM maintenance m JOIN equipment e ON e.equipment_id=m.equipment_id WHERE m.maintenance_id=10" \
 "In Progress,2026-10-10,Under Maintenance"

expect_error TC65 "sp_start_maintenance refuses a job that is not Scheduled" \
 "CALL sp_start_maintenance(10,'2026-10-10')" 1644

expect_value TC66 "sp_start_maintenance refuses work on an item that is with a student" \
 "INSERT INTO maintenance (maintenance_id, equipment_id, staff_id, maintenance_date, maintenance_type, maintenance_status)
  VALUES (901,1,2,'2026-10-10','Calibration','Scheduled');
  CALL sp_start_maintenance(901,'2026-10-10');" \
 "ERROR 1644 (45000) at line 3: Start refused: the equipment is currently allocated to a student; record its return first"

expect_value TC67 "sp_complete_maintenance records cost and makes the repaired item Available" \
 "CALL sp_complete_maintenance(10,900.00,'Good','USB connector replaced');
  SELECT CONCAT_WS(',',m.maintenance_status,m.maintenance_cost,e.equipment_condition,e.availability_status)
  FROM maintenance m JOIN equipment e ON e.equipment_id=m.equipment_id WHERE m.maintenance_id=10" \
 "Completed,900.00,Good,Available"

expect_error TC68 "sp_complete_maintenance refuses a missing cost" \
 "CALL sp_complete_maintenance(8,NULL,'Good',NULL)" 1644

expect_value TC69 "...and job 8 is unchanged (still In Progress, item still Under Maintenance)" \
 "SELECT CONCAT_WS(',',m.maintenance_status,e.availability_status)
  FROM maintenance m JOIN equipment e ON e.equipment_id=m.equipment_id WHERE m.maintenance_id=8" \
 "In Progress,Under Maintenance"

expect_value TC70 "With two jobs In Progress on one item, completing one keeps it Under Maintenance" \
 "INSERT INTO maintenance (maintenance_id, equipment_id, staff_id, maintenance_date, maintenance_type, maintenance_status)
  VALUES (902,3,2,'2026-10-10','Calibration','Scheduled');
  CALL sp_start_maintenance(902,'2026-10-10');
  CALL sp_complete_maintenance(8,8500.00,'Good','Input stage replaced');
  SELECT availability_status FROM equipment WHERE equipment_id=3" \
 "Under Maintenance"

q "DELETE FROM maintenance WHERE maintenance_id=901" >/dev/null
check_validation TC71 "After the maintenance workflow, validation still finds no violations"

# ---------- 10. register-number format (CHECK chk_student_register_no) ----
expect_error TC72 "Malformed register number '24BC1012' rejected (CHECK)" \
 "INSERT INTO student (student_name, register_number, department, year_of_study, email)
  VALUES ('Bad Register','24BC1012','CSE',2,'bad.register@students.example.edu')" 3819

expect_error TC73 "Lower-case register number '26bce1997' rejected (case-sensitive CHECK)" \
 "INSERT INTO student (student_name, register_number, department, year_of_study, email)
  VALUES ('Lower Case','26bce1997','CSE',1,'lower.case@students.example.edu')" 3819

expect_value TC74 "chk_student_register_no is declared and enforced on student" \
 "SELECT CONCAT_WS(',', tc.CONSTRAINT_NAME, tc.ENFORCED,
         (SELECT COUNT(*) FROM student WHERE NOT REGEXP_LIKE(register_number, '^[0-9]{2}[A-Z]{3}[0-9]{4}\$', 'c')))
  FROM information_schema.TABLE_CONSTRAINTS tc
  WHERE tc.TABLE_SCHEMA='${TEST_DB}' AND tc.TABLE_NAME='student'
    AND tc.CONSTRAINT_NAME='chk_student_register_no'" \
 "chk_student_register_no,YES,0"

# ---------- summary ---------------------------------------------------
if [ "${KEEP_TEST_DB:-0}" != 1 ]; then
    $MYSQL_CMD -e "DROP DATABASE IF EXISTS ${TEST_DB}"
fi
echo "---------------------------------------------------------------------"
echo "Passed: $PASS   Failed: $FAIL   Total: $((PASS + FAIL))"
[ "$FAIL" -eq 0 ]
