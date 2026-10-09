-- =====================================================================
-- File   : 11_transaction_procedures.sql
-- Purpose: Controlled, ATOMIC allocation and return operations.
--          These two stored procedures are the only intended way to
--          change equipment_allocation / equipment_return together with
--          equipment.availability_status (see docs/DESIGN_DECISIONS.md).
-- Run    : after 01-03:
--          mysql -u <user> -p < sql/11_transaction_procedures.sql
--
-- Why procedures?
--   Issuing equipment touches TWO tables (insert an allocation AND mark
--   the equipment 'Allocated'); a return touches THREE. If only part of
--   that work were saved the stored status would contradict the history.
--   Each procedure runs START TRANSACTION ... COMMIT and, on ANY error,
--   ROLLBACK + RESIGNAL, so either every change is saved or none is, and
--   the original error is still reported to the caller.
--
-- Concurrency:
--   Both procedures lock the equipment row first with SELECT ... FOR
--   UPDATE. A second session trying to allocate the same item waits for
--   the first to COMMIT, then re-reads the row, sees 'Allocated' and is
--   refused. The functional UNIQUE index on equipment_allocation is a
--   second, independent guard against two active allocations.
--   Lock order is always equipment -> allocation, which avoids deadlocks
--   between an allocation and a return of the same item.
--
-- Note: START TRANSACTION inside a procedure implicitly commits any
-- transaction the caller already had open; call these procedures
-- outside an explicit transaction.
--
-- Error convention: business-rule failures raise SQLSTATE '45000'
-- (MySQL error 1644) with a readable message.
-- =====================================================================

USE smart_lab_equipment_db;

DROP PROCEDURE IF EXISTS sp_allocate_equipment;
DROP PROCEDURE IF EXISTS sp_return_equipment;

DELIMITER $$

-- ---------------------------------------------------------------------
-- sp_allocate_equipment
--   1. lock and read the equipment row (does it exist? is it eligible?)
--   2. eligible  = availability_status 'Available' (which, by the CHECK
--      constraint, also means it is not Damaged)
--   3. insert the 'Issued' allocation (FKs validate student and staff;
--      the unique index rejects a conflicting active allocation)
--   4. set availability_status = 'Allocated'
--   5. COMMIT  (any error -> ROLLBACK)
-- p_allocation_date NULL means "today".
-- ---------------------------------------------------------------------
CREATE PROCEDURE sp_allocate_equipment(
    IN  p_equipment_id         INT,
    IN  p_student_id           INT,
    IN  p_staff_id             INT,
    IN  p_allocation_date      DATE,
    IN  p_expected_return_date DATE,
    OUT p_allocation_id        INT)
BEGIN
    DECLARE v_status    VARCHAR(20) DEFAULT NULL;
    DECLARE v_condition VARCHAR(20) DEFAULT NULL;
    DECLARE v_date      DATE        DEFAULT COALESCE(p_allocation_date, CURDATE());
    DECLARE v_message   VARCHAR(200);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    SET p_allocation_id = NULL;

    START TRANSACTION;

    -- Step 1: lock the equipment row for the rest of the transaction.
    SELECT availability_status, equipment_condition
      INTO v_status, v_condition
      FROM equipment
     WHERE equipment_id = p_equipment_id
       FOR UPDATE;

    IF v_status IS NULL THEN
        SET v_message = CONCAT('Allocation refused: equipment ', p_equipment_id, ' does not exist');
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
    END IF;

    -- Step 2: eligibility.
    IF v_status <> 'Available' THEN
        SET v_message = CONCAT('Allocation refused: equipment ', p_equipment_id,
                               ' is ', v_status, ', not Available');
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
    END IF;

    IF v_condition = 'Damaged' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Allocation refused: equipment is Damaged';
    END IF;

    IF p_expected_return_date IS NULL OR p_expected_return_date < v_date THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Allocation refused: expected return date must be on or after the allocation date';
    END IF;

    -- Step 3: record the allocation.
    INSERT INTO equipment_allocation
           (equipment_id, student_id, staff_id, allocation_date, expected_return_date, allocation_status)
    VALUES (p_equipment_id, p_student_id, p_staff_id, v_date, p_expected_return_date, 'Issued');

    SET p_allocation_id = LAST_INSERT_ID();

    -- Step 4: keep the stored availability consistent.
    UPDATE equipment
       SET availability_status = 'Allocated'
     WHERE equipment_id = p_equipment_id;

    -- Step 5: make both changes permanent together.
    COMMIT;
END$$

-- ---------------------------------------------------------------------
-- sp_return_equipment
--   1. find the allocation and lock its equipment row, then the
--      allocation row (lock order equipment -> allocation)
--   2. the allocation must exist and still be 'Issued'
--   3. return date must not be before the allocation date
--   4. insert the equipment_return row (UNIQUE allocation_id prevents a
--      second return for the same allocation)
--   5. mark the allocation 'Returned'
--   6. copy the return condition to the equipment; a Damaged item becomes
--      'Unavailable' until it is repaired, otherwise 'Available'
--   7. COMMIT  (any error -> ROLLBACK)
-- p_return_date NULL means "today".
-- ---------------------------------------------------------------------
CREATE PROCEDURE sp_return_equipment(
    IN p_allocation_id    INT,
    IN p_return_date      DATE,
    IN p_return_condition VARCHAR(20),
    IN p_remarks          VARCHAR(255))
BEGIN
    DECLARE v_equipment_id    INT         DEFAULT NULL;
    DECLARE v_alloc_status    VARCHAR(20) DEFAULT NULL;
    DECLARE v_allocation_date DATE        DEFAULT NULL;
    DECLARE v_locked_id       INT         DEFAULT NULL;
    DECLARE v_date            DATE        DEFAULT COALESCE(p_return_date, CURDATE());
    DECLARE v_message         VARCHAR(200);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    -- Step 1: which equipment does this allocation refer to?
    SELECT equipment_id INTO v_equipment_id
      FROM equipment_allocation
     WHERE allocation_id = p_allocation_id;

    IF v_equipment_id IS NULL THEN
        SET v_message = CONCAT('Return refused: allocation ', p_allocation_id, ' does not exist');
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
    END IF;

    -- Lock equipment first, then the allocation (same order as allocation).
    SELECT equipment_id INTO v_locked_id
      FROM equipment
     WHERE equipment_id = v_equipment_id
       FOR UPDATE;

    SELECT allocation_status, allocation_date
      INTO v_alloc_status, v_allocation_date
      FROM equipment_allocation
     WHERE allocation_id = p_allocation_id
       FOR UPDATE;

    -- Step 2: only an outstanding allocation can be returned.
    IF v_alloc_status <> 'Issued' THEN
        SET v_message = CONCAT('Return refused: allocation ', p_allocation_id, ' is already ', v_alloc_status);
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
    END IF;

    -- Step 3: date sanity (a cross-table rule a CHECK constraint cannot express).
    IF v_date < v_allocation_date THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Return refused: return date is before the allocation date';
    END IF;

    -- Step 4: record the return (CHECK validates p_return_condition).
    INSERT INTO equipment_return (allocation_id, return_date, return_condition, remarks)
    VALUES (p_allocation_id, v_date, p_return_condition, p_remarks);

    -- Step 5: close the allocation.
    UPDATE equipment_allocation
       SET allocation_status = 'Returned'
     WHERE allocation_id = p_allocation_id;

    -- Step 6: update the equipment's condition and availability.
    UPDATE equipment
       SET equipment_condition = p_return_condition,
           availability_status = IF(p_return_condition = 'Damaged', 'Unavailable', 'Available')
     WHERE equipment_id = v_equipment_id;

    -- Step 7.
    COMMIT;
END$$

DELIMITER ;

-- Confirm the procedures exist.
SELECT ROUTINE_NAME AS procedure_name, ROUTINE_TYPE AS routine_type
FROM   information_schema.ROUTINES
WHERE  ROUTINE_SCHEMA = 'smart_lab_equipment_db'
ORDER  BY ROUTINE_NAME;

-- ---------------------------------------------------------------------
-- USAGE EXAMPLES (commented out so that running this file never changes
-- data). Copy them into the mysql client to try them.
--
--   -- Issue the Network Cable Tester (equipment 15) to Nisha (student 10),
--   -- issued by Ramesh Kumar (staff 1):
--   CALL sp_allocate_equipment(15, 10, 1, '2026-10-10', '2026-10-17', @new_id);
--   SELECT @new_id;
--   SELECT availability_status FROM equipment WHERE equipment_id = 15;  -- Allocated
--
--   -- Try to issue the same item again -> ERROR 1644 ... is Allocated, not Available
--   CALL sp_allocate_equipment(15, 3, 1, '2026-10-10', '2026-10-17', @other_id);
--
--   -- Return it in good condition:
--   CALL sp_return_equipment(@new_id, '2026-10-10', 'Good', 'Returned complete');
--   SELECT availability_status FROM equipment WHERE equipment_id = 15;  -- Available
-- ---------------------------------------------------------------------
