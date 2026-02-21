-- Create a read-only user for the text-to-SQL analytics tool.
-- This user can only SELECT from tables, providing a security boundary
-- for LLM-generated SQL queries.
-- Password should be set via READONLY_PASSWORD environment variable
-- For development, pass a strong password via docker-compose secrets or env_file

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'bot_readonly') THEN
        -- CHANGE IN PRODUCTION
        CREATE ROLE bot_readonly WITH LOGIN PASSWORD 'your_very_secure_password_here';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE luxtick TO bot_readonly;
GRANT USAGE ON SCHEMA public TO bot_readonly;

-- Grant SELECT on all existing and future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO bot_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO bot_readonly;

-- Set a statement timeout for safety (5 seconds)
ALTER ROLE bot_readonly SET statement_timeout = '5s';
