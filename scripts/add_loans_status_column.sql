-- One-off fix: add missing loans.status column if your DB was never migrated with add_loan_status.
-- Run this if you get: column loans.status does not exist
-- Safe to run multiple times (IF NOT EXISTS).

ALTER TABLE loans
ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'active';
