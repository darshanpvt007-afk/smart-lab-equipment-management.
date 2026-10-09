-- =====================================================================
-- File   : 13_app_users.sql                       (added for deployment)
-- Purpose: Sign-in accounts and login throttling for the web application.
-- Run    : after 01-12, with the MIGRATION account (not the runtime one):
--          mysql -u <migration_user> -p < sql/13_app_users.sql
--
-- SAFE TO RE-RUN: only CREATE TABLE IF NOT EXISTS. It never drops,
-- truncates or changes existing tables or rows, so it can be applied to a
-- database that already holds real data (tests TC75-TC78).
--
-- These two tables belong to the application's security layer, not to the
-- Review 1 ER model; see docs/DESIGN_DECISIONS.md D-24.
--
-- No account is created here: there are no default users or passwords.
-- Create the first administrator with:   flask --app wsgi create-user
-- =====================================================================

USE smart_lab_equipment_db;

-- ---------------------------------------------------------------------
-- app_user: one row per person who can sign in.
--   password_hash : salted scrypt hash from werkzeug.security (never the password)
--   role          : admin | lab_manager | inventory_staff | technician
--                   (permissions are defined in app/auth.py, docs/SECURITY.md)
--   staff_id      : optional link to the lab_staff row of the same person
--   session_epoch : incremented on password change / deactivation; sessions
--                   that carry an older value are signed out
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app_user (
    user_id        INT          NOT NULL AUTO_INCREMENT,
    username       VARCHAR(40)  NOT NULL,
    password_hash  VARCHAR(255) NOT NULL,
    role           VARCHAR(20)  NOT NULL,
    staff_id       INT          NULL,
    is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
    session_epoch  INT          NOT NULL DEFAULT 0,
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at  DATETIME     NULL,
    CONSTRAINT pk_app_user          PRIMARY KEY (user_id),
    CONSTRAINT uq_app_user_username UNIQUE (username),
    CONSTRAINT chk_app_user_role    CHECK (role IN ('admin', 'lab_manager', 'inventory_staff', 'technician')),
    CONSTRAINT chk_app_user_name    CHECK (REGEXP_LIKE(username, '^[a-z0-9._-]{3,40}$', 'c')),
    CONSTRAINT fk_app_user_staff    FOREIGN KEY (staff_id)
        REFERENCES lab_staff (staff_id)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- login_attempt: recent sign-in attempts, used to slow down password
-- guessing (per username and per client address). Rows older than one
-- day are deleted by the application, so this is not a long-term log.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS login_attempt (
    attempt_id    BIGINT       NOT NULL AUTO_INCREMENT,
    username      VARCHAR(40)  NOT NULL,
    client_ip     VARCHAR(45)  NOT NULL,          -- IPv4 or IPv6 text
    succeeded     BOOLEAN      NOT NULL,
    attempted_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_login_attempt PRIMARY KEY (attempt_id),
    INDEX idx_login_attempt_user (username, attempted_at),   -- inside the table so a re-run
    INDEX idx_login_attempt_ip   (client_ip, attempted_at)   -- never fails on duplicate names
) ENGINE = InnoDB;
