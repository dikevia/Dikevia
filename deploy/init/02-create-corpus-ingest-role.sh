#!/bin/bash
set -euo pipefail
: "${POSTGRES_INGEST_PASSWORD:?POSTGRES_INGEST_PASSWORD must be set}"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=ingest_password="$POSTGRES_INGEST_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE cfdt_juris_ingest LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD %L', :'ingest_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='cfdt_juris_ingest')
\gexec
ALTER ROLE cfdt_juris_ingest LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD :'ingest_password';
GRANT CONNECT ON DATABASE cfdt_juris TO cfdt_juris_ingest;
GRANT USAGE ON SCHEMA public TO cfdt_juris_ingest;
SQL
