-- =====================================================================
-- File   : 12_maintenance_procedures.sql            (added in Review 3)
-- Purpose: Atomic maintenance workflow that keeps
--          equipment.availability_status consistent with maintenance.
-- Run    : after 01-03 (and 11):
--          mysql -u <user> -p < sql/12_maintenance_procedures.sql
--
-- Workflow of a maintenance job:
--   Scheduled   --sp_start_maintenance-->    In Progress
--   In Progress --sp_complete_maintenance--> Completed
-- Scheduling a job is a plain INSERT with maintenance_status 'Scheduled'
-- (it does not change availability: the item stays usable until work
-- actually starts).
--
-- Rules (see docs/DESIGN_DECISIONS.md D-08, D-11, D-20):
--   * work cannot start while the item is with a student ('Allocated')
--   * starting work sets the item 'Under Maintenance'
--   * completing work records the cost and the item's new condition;
--     the item becomes 'Available' (or 'Unavailable' if still Damaged)
--     unless another job on the same item is still In Progress
--
-- Same conventions as file 11: lock the equipment row first
-- (SELECT ... FOR UPDATE), ROLLBACK + RESIGNAL on any error, and
-- SQLSTATE '45000' (error 1644) for business-rule refusals.
-- =====================================================================

USE smart_lab_equipment_db;

DROP PROCEDURE IF EXISTS sp_start_maintenance;
DROP PROCEDURE IF EXISTS sp_complete_maintenance;

DELIMITER $$

-- ---------------------------------------------------------------------
-- sp_start_maintenance(maintenance_id, start_date)
--   start_date NULL means "today"; it becomes the job's maintenance_date.
-- ---------------------------------------------------------------------
CREATE PROCEDURE sp_start_maintenance(
    IN p_maintenance_id INT,
    IN p_start_date     DATE)
BEGIN
    DECLARE v_equipment_id INT         DEFAULT NULL;
    DECLARE v_job_status   VARCHAR(20) DEFAULT NULL;
    DECLARE v_availability VARCHAR(20) DEFAULT NULL;
    DECLARE v_date         DATE        DEFAULT COALESCE(p_start_date, CURDATE());
    DECLARE v_message      VARCHAR(200);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    SELECT equipment_id INTO v_equipment_id
      FROM maintenance
     WHERE maintenance_id = p_maintenance_id;

    IF v_equipment_id IS NULL THEN
        SET v_message = CONCAT('Start refused: maintenance record ', p_maintenance_id, ' does not exist');
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
    END IF;

    -- Lock order: equipment, then the maintenance row.
    SELECT availability_status INTO v_availability
      FROM equipment
     WHERE equipment_id = v_equipment_id
       FOR UPDATE;

    SELECT maintenance_status INTO v_job_status
      FROM maintenance
     WHERE maintenance_id = p_maintenance_id
       FOR UPDATE;

    IF v_job_status <> 'Scheduled' THEN
        SET v_message = CONCAT('Start refused: maintenance ', p_maintenance_id, ' is ', v_job_status, ', not Scheduled');
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
    END IF;

    IF v_availability = 'Allocated' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Start refused: the equipment is currently allocated to a student; record its return first';
    END IF;

    UPDATE maintenance
       SET maintenance_status = 'In Progress',
           maintenance_date   = v_date
     WHERE maintenance_id = p_maintenance_id;

    UPDATE equipment
       SET availability_status = 'Under Maintenance'
     WHERE equipment_id = v_equipment_id;

    COMMIT;
END$$

-- ---------------------------------------------------------------------
-- sp_complete_maintenance(maintenance_id, cost, condition_after, remarks)
--   condition_after: the equipment's condition when the job ends
--   ('New', 'Good', 'Fair' or 'Damaged' if it could not be repaired).
--   remarks NULL keeps the existing remarks.
-- ---------------------------------------------------------------------
CREATE PROCEDURE sp_complete_maintenance(
    IN p_maintenance_id  INT,
    IN p_cost            DECIMAL(10,2),
    IN p_condition_after VARCHAR(20),
    IN p_remarks         VARCHAR(255))
BEGIN
    DECLARE v_equipment_id INT         DEFAULT NULL;
    DECLARE v_job_status   VARCHAR(20) DEFAULT NULL;
    DECLARE v_locked_id    INT         DEFAULT NULL;
    DECLARE v_other_jobs   INT         DEFAULT 0;
    DECLARE v_message      VARCHAR(200);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    SELECT equipment_id INTO v_equipment_id
      FROM maintenance
     WHERE maintenance_id = p_maintenance_id;

    IF v_equipment_id IS NULL THEN
        SET v_message = CONCAT('Completion refused: maintenance record ', p_maintenance_id, ' does not exist');
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
    END IF;

    SELECT equipment_id INTO v_locked_id
      FROM equipment
     WHERE equipment_id = v_equipment_id
       FOR UPDATE;

    SELECT maintenance_status INTO v_job_status
      FROM maintenance
     WHERE maintenance_id = p_maintenance_id
       FOR UPDATE;

    IF v_job_status <> 'In Progress' THEN
        SET v_message = CONCAT('Completion refused: maintenance ', p_maintenance_id, ' is ', v_job_status, ', not In Progress');
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
    END IF;

    IF p_cost IS NULL OR p_cost < 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Completion refused: a completed job needs a cost of 0 or more';
    END IF;

    UPDATE maintenance
       SET maintenance_status = 'Completed',
           maintenance_cost   = p_cost,
           remarks            = COALESCE(p_remarks, remarks)
     WHERE maintenance_id = p_maintenance_id;

    -- Another job on the same item may still be running.
    SELECT COUNT(*) INTO v_other_jobs
      FROM maintenance
     WHERE equipment_id = v_equipment_id
       AND maintenance_status = 'In Progress';

    -- The CHECK constraint on equipment validates p_condition_after.
    UPDATE equipment
       SET equipment_condition = p_condition_after,
           availability_status = CASE
               WHEN v_other_jobs > 0              THEN 'Under Maintenance'
               WHEN p_condition_after = 'Damaged' THEN 'Unavailable'
               ELSE 'Available'
           END
     WHERE equipment_id = v_equipment_id;

    COMMIT;
END$$

DELIMITER ;

SELECT ROUTINE_NAME AS procedure_name
FROM   information_schema.ROUTINES
WHERE  ROUTINE_SCHEMA = 'smart_lab_equipment_db'
ORDER  BY ROUTINE_NAME;

-- ---------------------------------------------------------------------
-- USAGE EXAMPLES (commented out; they change data)
--   -- Finish the in-progress calibration of power supply 17:
--   CALL sp_complete_maintenance(9, 1200.00, 'Good', 'Calibrated within tolerance');
--   -- Start the scheduled USB-connector repair of Arduino kit 9:
--   CALL sp_start_maintenance(10, '2026-10-15');
-- ---------------------------------------------------------------------
