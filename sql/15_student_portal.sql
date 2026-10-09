-- =====================================================================
-- File   : 15_student_portal.sql                 (added after deployment)
-- Purpose: Student sign-in (self-activated accounts) and equipment
--          borrowing requests that staff approve or reject.
-- Run    : after 01-13, with the MIGRATION account:
--          mysql -u <migration_user> -p < sql/15_student_portal.sql
--
-- SAFE TO RE-RUN: only CREATE TABLE IF NOT EXISTS (indexes inside the
-- table definitions). Never drops or changes existing tables or rows.
-- See docs/DESIGN_DECISIONS.md D-25 and docs/SECURITY.md section 7.
--
-- No student account is created here. An administrator opens activation
-- on the Users > Student sign-in page; each student then activates once
-- with their register number + e-mail on record and chooses a password.
-- =====================================================================

USE smart_lab_equipment_db;

-- ---------------------------------------------------------------------
-- student_account: at most one per student.
--   Pending   : password_hash IS NULL, activation_expires_at in the future
--   Active    : password_hash set (salted scrypt hash, never the password)
--   is_active = FALSE switches the account off without deleting it.
--   session_epoch: incremented on reset/deactivation; older sessions end.
-- The account is meaningless without its student, so it is deleted with
-- the student (CASCADE); every other student link stays RESTRICT.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS student_account (
    student_id            INT          NOT NULL,
    password_hash         VARCHAR(255) NULL,
    is_active             BOOLEAN      NOT NULL DEFAULT TRUE,
    session_epoch         INT          NOT NULL DEFAULT 0,
    activation_expires_at DATETIME     NULL,
    activated_at          DATETIME     NULL,
    last_login_at         DATETIME     NULL,
    created_at            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_student_account PRIMARY KEY (student_id),
    -- a pending account (no password yet) must have an activation deadline
    CONSTRAINT chk_student_account_state
        CHECK (password_hash IS NOT NULL OR activation_expires_at IS NOT NULL),
    CONSTRAINT fk_student_account_student FOREIGN KEY (student_id)
        REFERENCES student (student_id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- equipment_request: a student asks to borrow one available item.
--   Pending -> Approved (staff issued it: allocation_id is set)
--           -> Rejected (staff, optional note)
--           -> Cancelled (by the student)
-- One pending request per student and item (functional unique index,
-- like the one-active-allocation rule in file 02).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS equipment_request (
    request_id          INT          NOT NULL AUTO_INCREMENT,
    student_id          INT          NOT NULL,
    equipment_id        INT          NOT NULL,
    requested_from      DATE         NOT NULL,
    requested_until     DATE         NOT NULL,
    purpose             VARCHAR(255) NOT NULL,
    request_status      VARCHAR(20)  NOT NULL DEFAULT 'Pending',
    created_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_by_user_id  INT          NULL,
    decided_at          DATETIME     NULL,
    decision_note       VARCHAR(255) NULL,
    allocation_id       INT          NULL,
    CONSTRAINT pk_equipment_request      PRIMARY KEY (request_id),
    CONSTRAINT chk_request_status        CHECK (request_status IN ('Pending', 'Approved', 'Rejected', 'Cancelled')),
    CONSTRAINT chk_request_dates         CHECK (requested_until >= requested_from),
    CONSTRAINT chk_request_approved_link CHECK (request_status <> 'Approved' OR allocation_id IS NOT NULL),
    CONSTRAINT fk_request_student    FOREIGN KEY (student_id)   REFERENCES student (student_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_request_equipment  FOREIGN KEY (equipment_id) REFERENCES equipment (equipment_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_request_decided_by FOREIGN KEY (decided_by_user_id) REFERENCES app_user (user_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    -- ON UPDATE RESTRICT: MySQL does not allow a column used in a CHECK
    -- (chk_request_approved_link) to have a cascading referential action.
    CONSTRAINT fk_request_allocation FOREIGN KEY (allocation_id) REFERENCES equipment_allocation (allocation_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    UNIQUE KEY uq_request_one_pending (
        (CASE WHEN request_status = 'Pending' THEN student_id END),
        (CASE WHEN request_status = 'Pending' THEN equipment_id END)),
    INDEX idx_request_status (request_status, created_at)
) ENGINE = InnoDB;
