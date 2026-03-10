-- xampp_setup.sql
-- Run this in XAMPP phpMyAdmin → SQL tab, OR via MySQL command line
-- This creates the database. Django creates the tables automatically.

CREATE DATABASE IF NOT EXISTS lbas_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- Confirm it worked:
SHOW DATABASES LIKE 'lbas_db';
