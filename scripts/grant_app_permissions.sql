-- Run this script as a PostgreSQL superuser (e.g. postgres) to grant the app user
-- access to all tables. Fixes: "permission denied for table contents/admins/..."
--
-- Usage (from host where Postgres runs):
--   psql -U postgres -d payment_db -f scripts/grant_app_permissions.sql
-- Or from inside a postgres container:
--   docker exec -i <postgres_container> psql -U postgres -d payment_db < scripts/grant_app_permissions.sql

\echo 'Granting permissions to payment_user on payment_db...'

-- Ensure app user can use the schema
GRANT USAGE ON SCHEMA public TO payment_user;

-- Grant full DML on all existing tables in public
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO payment_user;

-- Allow app user to use sequences (for SERIAL/identity columns)
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO payment_user;

-- Optional: grant on future tables (PostgreSQL 9.0+)
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO payment_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO payment_user;

\echo 'Done. If you use a different app username, replace payment_user in this script and re-run.'
