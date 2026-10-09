-- =====================================================================
-- Smart Laboratory Equipment Inventory, Allocation and Maintenance
-- Management System -- Review 2: Database Design & SQL Implementation
--
-- File   : 01_create_database.sql
-- Purpose: Create the project database with the utf8mb4 character set.
-- Target : MySQL 8.0 (tested on MySQL 8.0.46)
--
-- Run    : mysql -u <user> -p < sql/01_create_database.sql
-- Safe to re-run: IF NOT EXISTS means an existing database is NOT touched.
-- =====================================================================

CREATE DATABASE IF NOT EXISTS smart_lab_equipment_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;

USE smart_lab_equipment_db;

-- Confirm the database and its character set.
SELECT SCHEMA_NAME                AS database_name,
       DEFAULT_CHARACTER_SET_NAME AS character_set,
       DEFAULT_COLLATION_NAME     AS collation_name
FROM   information_schema.SCHEMATA
WHERE  SCHEMA_NAME = 'smart_lab_equipment_db';
