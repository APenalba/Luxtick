-- Create the test database used by pytest.
-- This script is mounted in docker-entrypoint-initdb.d/ and runs
-- automatically on first container start (fresh volume).
--
-- Depends on: init-readonly-user.sql (creates bot_readonly role)

CREATE DATABASE luxtick_test;

-- Grant full access to the main bot user (already exists as POSTGRES_USER)
GRANT ALL PRIVILEGES ON DATABASE luxtick_test TO bot;

-- Grant connect access to the readonly user
GRANT CONNECT ON DATABASE luxtick_test TO bot_readonly;
