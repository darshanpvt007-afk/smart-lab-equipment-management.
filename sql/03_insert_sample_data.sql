-- =====================================================================
-- File   : 03_insert_sample_data.sql
-- Purpose: Realistic, internally consistent sample data.
-- Run after 02_create_tables.sql:
--     mysql -u <user> -p < sql/03_insert_sample_data.sql
--
-- All people, companies, e-mail addresses and phone numbers are
-- FICTIONAL. E-mail domains use the reserved "example" domains.
-- Dates are ISO format (YYYY-MM-DD). Amounts are in INR.
--
-- Primary key values are written explicitly so that the foreign key
-- values below are easy to read and explain. AUTO_INCREMENT continues
-- from the highest value for any later insert.
--
-- The data describes the state of the labs on the review reference
-- date 2026-10-10 (see docs/DESIGN_DECISIONS.md, D-09):
--   * 20 allocations: 14 returned (with return rows), 6 still issued
--   * 3 of the 6 issued allocations are overdue on 2026-10-10
--   * equipment.availability_status agrees with the allocation and
--     maintenance history (checked by 09_validation_queries.sql)
--
-- Everything runs in one transaction: either all rows load or none do.
-- =====================================================================

USE smart_lab_equipment_db;

START TRANSACTION;

-- ---------------------------------------------------------------------
-- Parent tables (no foreign keys)
-- ---------------------------------------------------------------------
INSERT INTO lab (lab_id, lab_name, location, capacity, lab_type) VALUES
 (1, 'Computer Networks Lab',      'Block A, Room 101', 40, 'Computer'),
 (2, 'Electronics and Circuits Lab','Block B, Room 204', 36, 'Electronics'),
 (3, 'Applied Physics Lab',       'Block C, Room 012', 30, 'Physics'),
 (4, 'Embedded Systems Lab',      'Block B, Room 210', 24, 'Electronics');

INSERT INTO equipment_category (category_id, category_name, description) VALUES
 (1, 'Oscilloscope',        'Instruments for viewing and measuring electrical waveforms'),
 (2, 'Multimeter',          'Handheld meters for voltage, current and resistance'),
 (3, 'Microcontroller Kit', 'Development boards and starter kits for embedded programming'),
 (4, 'Networking Device',   'Switches, routers and network test tools'),
 (5, 'Power Supply',        'Regulated and programmable DC power sources'),
 (6, 'Optical Instrument',  'Spectrometers, diffraction kits and other optics apparatus');

INSERT INTO supplier (supplier_id, supplier_name, contact_number, email, address) VALUES
 (1, 'Apex Scientific Instruments Pvt Ltd', '9000000101', 'sales@apex-scientific.example.com', '14 Industrial Estate Road, Chennai'),
 (2, 'TechNova Electronics Supplies',       '9000000102', 'orders@technova.example.com',       '221 Electronics Market, Bengaluru'),
 (3, 'Orbit Lab Equipment Traders',         '9000000103', 'contact@orbitlab.example.com',      '7 Science Park Avenue, Hyderabad'),
 (4, 'Zenith Network Solutions',            '9000000104', 'support@zenithnet.example.com',     '55 Tech Corridor, Pune');

INSERT INTO student (student_id, student_name, register_number, department, year_of_study, email) VALUES
 ( 1, 'Aarav Menon',      '24BCE1012', 'CSE', 3, 'aarav.menon@students.example.edu'),
 ( 2, 'Diya Raghavan',    '24BEC1045', 'ECE', 3, 'diya.raghavan@students.example.edu'),
 ( 3, 'Kabir Nair',       '25BCE1103', 'CSE', 2, 'kabir.nair@students.example.edu'),
 ( 4, 'Meera Iyer',       '23BEE1021', 'EEE', 4, 'meera.iyer@students.example.edu'),
 ( 5, 'Rohan Kulkarni',   '25BEC1077', 'ECE', 2, 'rohan.kulkarni@students.example.edu'),
 ( 6, 'Sneha Pillai',     '26BCE1150', 'CSE', 1, 'sneha.pillai@students.example.edu'),
 ( 7, 'Vikram Joshi',     '23BCE1009', 'CSE', 4, 'vikram.joshi@students.example.edu'),
 ( 8, 'Ananya Desai',     '24BEE1033', 'EEE', 3, 'ananya.desai@students.example.edu'),
 ( 9, 'Ishaan Rao',       '25BCE1118', 'CSE', 2, 'ishaan.rao@students.example.edu'),
 (10, 'Nisha Fernandes',  '26BEC1062', 'ECE', 1, 'nisha.fernandes@students.example.edu');

INSERT INTO lab_staff (staff_id, staff_name, designation, department, contact_number, email) VALUES
 (1, 'Ramesh Kumar',    'Lab Technician',          'CSE',     '9000000201', 'ramesh.kumar@staff.example.edu'),
 (2, 'Priya Sundaram',  'Senior Lab Assistant',    'ECE',     '9000000202', 'priya.sundaram@staff.example.edu'),
 (3, 'Suresh Babu',     'Lab Technician',          'EEE',     '9000000203', 'suresh.babu@staff.example.edu'),
 (4, 'Kavitha Ramesh',  'Lab In-charge',           'Physics', '9000000204', 'kavitha.ramesh@staff.example.edu');

-- ---------------------------------------------------------------------
-- purchase -> supplier
-- Purchase 7 is still 'Ordered', so no equipment refers to it yet.
-- ---------------------------------------------------------------------
INSERT INTO purchase (purchase_id, supplier_id, purchase_date, invoice_number, total_amount, purchase_status) VALUES
 (1, 1, '2025-06-10', 'ASI-2025-0141', 105000.00, 'Received'),
 (2, 2, '2025-07-22', 'TNE-2025-0388',  24200.00, 'Received'),
 (3, 1, '2025-11-05', 'ASI-2025-0517', 103500.00, 'Received'),
 (4, 4, '2026-01-14', 'ZNS-2026-0023',  68700.00, 'Received'),
 (5, 3, '2026-02-20', 'OLE-2026-0076',  72500.00, 'Received'),
 (6, 2, '2026-06-03', 'TNE-2026-0219',  14800.00, 'Received'),
 (7, 3, '2026-09-28', 'OLE-2026-0301',  46000.00, 'Ordered');

-- ---------------------------------------------------------------------
-- equipment -> equipment_category, lab, purchase
-- Current state on 2026-10-10:
--   Allocated         : 1, 4, 8, 10, 12, 14  (each has one 'Issued' allocation)
--   Under Maintenance : 3, 17                (each has an 'In Progress' job)
--   Unavailable       : 9                    (returned Damaged; repair scheduled)
--   Available         : all others
-- ---------------------------------------------------------------------
INSERT INTO equipment (equipment_id, equipment_name, serial_number, equipment_condition, availability_status, category_id, lab_id, purchase_id) VALUES
 ( 1, 'Digital Storage Oscilloscope 100 MHz', 'OSC-DS1-0001', 'Good',    'Allocated',         1, 2, 1),
 ( 2, 'Digital Storage Oscilloscope 100 MHz', 'OSC-DS1-0002', 'Good',    'Available',         1, 2, 1),
 ( 3, 'Mixed Signal Oscilloscope 200 MHz',    'OSC-MS2-0003', 'Damaged', 'Under Maintenance', 1, 4, 3),
 ( 4, 'Digital Multimeter',                   'DMM-17B-0004', 'Good',    'Allocated',         2, 2, 2),
 ( 5, 'Digital Multimeter',                   'DMM-17B-0005', 'Good',    'Available',         2, 2, 2),
 ( 6, 'Digital Multimeter',                   'DMM-17B-0006', 'Fair',    'Available',         2, 3, 2),
 ( 7, 'Clamp Meter',                          'CLM-32-0007',  'New',     'Available',         2, 3, 6),
 ( 8, 'Arduino Uno Starter Kit',              'MCU-ARD-0008', 'Good',    'Allocated',         3, 4, 2),
 ( 9, 'Arduino Uno Starter Kit',              'MCU-ARD-0009', 'Damaged', 'Unavailable',       3, 4, 2),
 (10, 'Raspberry Pi 4 Kit',                   'MCU-RPI-0010', 'New',     'Allocated',         3, 4, 6),
 (11, 'STM32 Nucleo Development Board',       'MCU-STM-0011', 'New',     'Available',         3, 4, 6),
 (12, 'Managed Layer-2 Switch 24-Port',       'NET-SW24-0012','Good',    'Allocated',         4, 1, 4),
 (13, 'Managed Layer-2 Switch 24-Port',       'NET-SW24-0013','Fair',    'Available',         4, 1, 4),
 (14, 'Wireless Router',                      'NET-WR-0014',  'Good',    'Allocated',         4, 1, 4),
 (15, 'Network Cable Tester',                 'NET-CT-0015',  'Good',    'Available',         4, 1, 4),
 (16, 'DC Regulated Power Supply 30V 5A',     'PSU-DC30-0016','Good',    'Available',         5, 2, 1),
 (17, 'DC Regulated Power Supply 30V 5A',     'PSU-DC30-0017','Good',    'Under Maintenance', 5, 3, 1),
 (18, 'Programmable DC Power Supply',         'PSU-PRG-0018', 'Good',    'Available',         5, 4, 3),
 (19, 'Spectrometer',                         'OPT-SPM-0019', 'Good',    'Available',         6, 3, 5),
 (20, 'Laser Diffraction Kit',                'OPT-LDK-0020', 'Good',    'Available',         6, 3, 5);

-- ---------------------------------------------------------------------
-- equipment_allocation -> equipment, student, lab_staff
-- Allocations 1-14 are 'Returned'; 15-20 are 'Issued' (outstanding).
-- No equipment has two allocations whose periods overlap.
-- ---------------------------------------------------------------------
INSERT INTO equipment_allocation (allocation_id, equipment_id, student_id, staff_id, allocation_date, expected_return_date, allocation_status) VALUES
 ( 1,  2, 1, 2, '2026-07-06', '2026-07-13', 'Returned'),
 ( 2,  4, 2, 2, '2026-07-08', '2026-07-15', 'Returned'),
 ( 3,  9, 5, 2, '2026-07-20', '2026-07-27', 'Returned'),
 ( 4, 12, 1, 1, '2026-07-22', '2026-07-29', 'Returned'),
 ( 5, 16, 4, 3, '2026-08-03', '2026-08-10', 'Returned'),
 ( 6, 19, 7, 4, '2026-08-05', '2026-08-12', 'Returned'),
 ( 7,  1, 2, 2, '2026-08-10', '2026-08-17', 'Returned'),
 ( 8, 13, 9, 1, '2026-08-12', '2026-08-19', 'Returned'),
 ( 9,  3, 7, 2, '2026-08-18', '2026-08-25', 'Returned'),
 (10,  5, 1, 3, '2026-08-24', '2026-08-31', 'Returned'),
 (11,  8, 3, 3, '2026-08-26', '2026-09-02', 'Returned'),
 (12, 14, 9, 1, '2026-09-01', '2026-09-08', 'Returned'),
 (13,  9, 6, 3, '2026-09-07', '2026-09-14', 'Returned'),
 (14, 20, 8, 4, '2026-09-10', '2026-09-17', 'Returned'),
 (15, 12, 7, 1, '2026-09-21', '2026-09-28', 'Issued'),   -- overdue on 2026-10-10
 (16,  4, 5, 2, '2026-09-28', '2026-10-05', 'Issued'),   -- overdue on 2026-10-10
 (17,  1, 1, 2, '2026-10-01', '2026-10-08', 'Issued'),   -- overdue on 2026-10-10
 (18,  8, 3, 3, '2026-10-05', '2026-10-12', 'Issued'),
 (19, 10, 9, 3, '2026-10-06', '2026-10-13', 'Issued'),
 (20, 14, 2, 1, '2026-10-07', '2026-10-14', 'Issued');

-- ---------------------------------------------------------------------
-- equipment_return -> equipment_allocation (one row per returned allocation)
-- ---------------------------------------------------------------------
INSERT INTO equipment_return (return_id, allocation_id, return_date, return_condition, remarks) VALUES
 ( 1,  1, '2026-07-12', 'Good',    'Returned with all probes'),
 ( 2,  2, '2026-07-15', 'Good',    NULL),
 ( 3,  3, '2026-07-27', 'Good',    NULL),
 ( 4,  4, '2026-07-30', 'Good',    'Returned one day late'),
 ( 5,  5, '2026-08-08', 'Good',    NULL),
 ( 6,  6, '2026-08-12', 'Fair',    'Minor misalignment of the eyepiece housing'),
 ( 7,  7, '2026-08-17', 'Good',    NULL),
 ( 8,  8, '2026-08-18', 'Fair',    'Two ports show intermittent link loss'),
 ( 9,  9, '2026-08-24', 'Damaged', 'Channel 2 input not responding'),
 (10, 10, '2026-08-29', 'Good',    NULL),
 (11, 11, '2026-09-02', 'Good',    'All components present'),
 (12, 12, '2026-09-07', 'Good',    NULL),
 (13, 13, '2026-09-16', 'Damaged', 'USB connector broken; returned two days late'),
 (14, 14, '2026-09-17', 'Good',    NULL);

-- ---------------------------------------------------------------------
-- maintenance -> equipment, lab_staff
-- Mix of Completed / In Progress / Scheduled. Scheduled jobs have no
-- cost yet (NULL). Equipment 4,6,7,8,10,11,14,15,18,20 have no
-- maintenance history.
-- ---------------------------------------------------------------------
INSERT INTO maintenance (maintenance_id, equipment_id, staff_id, maintenance_date, maintenance_type, maintenance_cost, maintenance_status, remarks) VALUES
 ( 1,  1, 2, '2026-06-15', 'Calibration', 1500.00, 'Completed',   'Annual calibration of vertical scale'),
 ( 2,  2, 2, '2026-06-15', 'Calibration', 1500.00, 'Completed',   'Annual calibration of vertical scale'),
 ( 3, 16, 3, '2026-07-20', 'Preventive',   600.00, 'Completed',   'Cooling fan cleaned; output voltage verified'),
 ( 4, 12, 1, '2026-08-04', 'Preventive',   450.00, 'Completed',   'Firmware updated; configuration reset'),
 ( 5, 19, 4, '2026-08-14', 'Repair',      3200.00, 'Completed',   'Eyepiece housing realigned after return'),
 ( 6, 13, 1, '2026-08-20', 'Preventive',   450.00, 'Completed',   'Port diagnostics run; two ports re-seated'),
 ( 7,  1, 2, '2026-09-02', 'Repair',      2750.00, 'Completed',   'Faulty power switch replaced'),
 ( 8,  3, 2, '2026-09-30', 'Repair',      8500.00, 'In Progress', 'Channel 2 input stage replacement; awaiting part'),
 ( 9, 17, 4, '2026-10-06', 'Calibration', 1200.00, 'In Progress', 'Output calibration against reference meter'),
 (10,  9, 3, '2026-10-15', 'Repair',         NULL, 'Scheduled',   'Replace broken USB connector'),
 (11,  5, 3, '2026-10-20', 'Calibration',    NULL, 'Scheduled',   'Routine semester calibration');

COMMIT;

-- Row counts after loading.
SELECT 'lab' AS table_name, COUNT(*) AS row_count FROM lab
UNION ALL SELECT 'equipment_category',   COUNT(*) FROM equipment_category
UNION ALL SELECT 'supplier',             COUNT(*) FROM supplier
UNION ALL SELECT 'purchase',             COUNT(*) FROM purchase
UNION ALL SELECT 'student',              COUNT(*) FROM student
UNION ALL SELECT 'lab_staff',            COUNT(*) FROM lab_staff
UNION ALL SELECT 'equipment',            COUNT(*) FROM equipment
UNION ALL SELECT 'equipment_allocation', COUNT(*) FROM equipment_allocation
UNION ALL SELECT 'equipment_return',     COUNT(*) FROM equipment_return
UNION ALL SELECT 'maintenance',          COUNT(*) FROM maintenance;
