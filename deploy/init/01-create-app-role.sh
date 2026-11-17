#!/bin/bash
set -euo pipefail
: "${POSTGRES_APP_PASSWORD:?POSTGRES_APP_PASSWORD must be set}"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=app_password="$POSTGRES_APP_PASSWORD" <<'SQL'
CREATE ROLE cfdt_juris_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS
  PASSWORD :'app_password';
GRANT CONNECT ON DATABASE cfdt_juris TO cfdt_juris_app;
GRANT USAGE ON SCHEMA public TO cfdt_juris_app;
SQL
