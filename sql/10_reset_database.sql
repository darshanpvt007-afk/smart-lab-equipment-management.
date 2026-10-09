-- =====================================================================
-- File   : 10_reset_database.sql
--
--   !!!  DESTRUCTIVE  !!!
--   This script DELETES the whole smart_lab_equipment_db database:
--   every table, view, procedure and ALL DATA in it. It cannot be undone.
--
-- Purpose: return a DEVELOPMENT machine to a clean state so that
--          01 -> 11 can be run again from scratch.
--
-- It is never run by any other script. Run it only deliberately:
--     mysql -u <user> -p < sql/10_reset_database.sql
-- then rebuild:
--     01_create_database.sql, 02_create_tables.sql, 03_insert_sample_data.sql,
--     08_create_views.sql, 11_transaction_procedures.sql
--
-- Take a backup first if the database holds anything you want to keep:
--     mysqldump -u <user> -p --routines smart_lab_equipment_db > backup.sql
-- =====================================================================

DROP DATABASE IF EXISTS smart_lab_equipment_db;

SELECT 'smart_lab_equipment_db has been dropped. Re-run the setup scripts to rebuild it.' AS reset_status;
