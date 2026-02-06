-- Run this script as a PostgreSQL superuser (e.g. postgres) to grant the app user
-- access to all tables. Fixes: "permission denied for table admins/contents/..."
--
-- Usage (from host where Postgres runs, e.g. your Mac):
--   cd payment_app && psql -U postgres -d payment_db -f scripts/grant_app_permissions.sql
--
-- If Postgres runs in Docker:
--   docker exec -i <postgres_container> psql -U postgres -d payment_db < scripts/grant_app_permissions.sql
--
-- If your app uses a different DB user, replace payment_user below and re-run.

\echo 'Granting permissions to payment_user on payment_db...'

-- Ensure app user can use the schema
GRANT USAGE ON SCHEMA public TO payment_user;

-- Give ownership of all tables to payment_user so Alembic migrations can run
-- (ALTER TABLE requires table ownership; otherwise: "must be owner of table X")
DO $$
DECLARE
  r RECORD;
BEGIN
  FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public')
  LOOP
    EXECUTE format('ALTER TABLE %I OWNER TO payment_user', r.tablename);
  END LOOP;
END $$;

-- Grant full DML on all existing tables in public
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO payment_user;

-- Allow app user to use sequences (for SERIAL/identity columns)
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO payment_user;

-- Optional: grant on future tables (PostgreSQL 9.0+)
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO payment_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO payment_user;

\echo 'Done. If you use a different app username, replace payment_user in this script and re-run.'
