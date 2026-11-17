#!/bin/bash
set -euo pipefail
: "${POSTGRES_PLATFORM_ADMIN_PASSWORD:?POSTGRES_PLATFORM_ADMIN_PASSWORD must be set}"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=platform_admin_password="$POSTGRES_PLATFORM_ADMIN_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE cfdt_juris_platform_admin LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD %L', :'platform_admin_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='cfdt_juris_platform_admin')
\gexec
ALTER ROLE cfdt_juris_platform_admin LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD :'platform_admin_password';
GRANT CONNECT ON DATABASE cfdt_juris TO cfdt_juris_platform_admin;
GRANT USAGE ON SCHEMA public TO cfdt_juris_platform_admin;
SQL
