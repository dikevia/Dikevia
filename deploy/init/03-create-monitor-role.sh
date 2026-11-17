#!/bin/bash
set -euo pipefail
: "${POSTGRES_MONITOR_PASSWORD:?POSTGRES_MONITOR_PASSWORD must be set}"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=monitor_password="$POSTGRES_MONITOR_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE cfdt_juris_monitor LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD %L', :'monitor_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='cfdt_juris_monitor')
\gexec
ALTER ROLE cfdt_juris_monitor LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD :'monitor_password';
GRANT CONNECT ON DATABASE cfdt_juris TO cfdt_juris_monitor;
GRANT pg_monitor TO cfdt_juris_monitor;
SQL
