#!/usr/bin/env bash
set -Eeuo pipefail

# DESTRUCTIVE: replaces the target database contents. Use only after verifying backup.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
ENV_FILE="${ENV_FILE:-.env}"
COMPOSE_FILE="${COMPOSE_FILE:-deploy/docker-compose.yml}"

BACKUP_FILE="${1:-}"
TARGET_DB="${TARGET_DB:-cfdt_juris}"
[[ -f "$ENV_FILE" ]] || { echo "Missing $ENV_FILE." >&2; exit 2; }
if [[ -z "${COMPOSE_PROJECT_NAME:-}" ]]; then
  COMPOSE_PROJECT_NAME="$(sed -n 's/^COMPOSE_PROJECT_NAME=//p' "$ENV_FILE" | tail -n 1)"
  COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-cfdt-juris}"
fi
if [[ "$ENV_FILE" == ".env.staging" ]]; then
  python3 scripts/upgrade_env_file.py --staging
  RUNTIME_ENV_FILE=".env.staging.runtime"
else
  python3 scripts/upgrade_env_file.py
  RUNTIME_ENV_FILE=".env.runtime"
fi
python3 scripts/render_runtime_env.py --source "$ENV_FILE" --output "$RUNTIME_ENV_FILE"
[[ -n "$BACKUP_FILE" && -s "$BACKUP_FILE" ]] || { echo "Usage: $0 path/to/backup.dump" >&2; exit 2; }
[[ "$TARGET_DB" =~ ^[A-Za-z_][A-Za-z0-9_]{0,62}$ ]] || { echo "Invalid TARGET_DB identifier." >&2; exit 2; }
command -v sha256sum >/dev/null
if [[ -f "${BACKUP_FILE}.sha256" ]]; then
  (cd "$(dirname "$BACKUP_FILE")" && sha256sum -c "$(basename "${BACKUP_FILE}.sha256")")
else
  echo "WARNING: no adjacent SHA256 file; integrity cannot be checked automatically." >&2
fi
printf 'This will DROP and recreate objects in database %s. Type RESTORE to continue: ' "$TARGET_DB"
read -r CONFIRM
[[ "$CONFIRM" == "RESTORE" ]] || { echo "Cancelled."; exit 1; }
ENV_FILE="$ENV_FILE" COMPOSE_PROJECT_NAME="$COMPOSE_PROJECT_NAME" COMPOSE_FILE="$COMPOSE_FILE" scripts/ensure_operational_roles.sh
# Ensure the database exists and the dump can be listed before destructive work.
docker compose -p "$COMPOSE_PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
  pg_restore --list < "$BACKUP_FILE" >/dev/null
# Restore with DBA/migration account; disconnect sessions before replacing objects.
docker compose -p "$COMPOSE_PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
  psql -U cfdt_migration -d postgres -v ON_ERROR_STOP=1 \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$TARGET_DB' AND pid <> pg_backend_pid();" \
  -c "DROP DATABASE IF EXISTS \"$TARGET_DB\";" \
  -c "CREATE DATABASE \"$TARGET_DB\" OWNER cfdt_migration;"
docker compose -p "$COMPOSE_PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
  pg_restore -U cfdt_migration -d "$TARGET_DB" --clean --if-exists --no-owner --no-acl < "$BACKUP_FILE"
docker compose -p "$COMPOSE_PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
  psql -U cfdt_migration -d "$TARGET_DB" -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/05-runtime-grants.sql
echo "Restore completed. Runtime and corpus-ingest grants reapplied; verify /ready and tenant isolation."
