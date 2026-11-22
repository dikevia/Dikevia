#!/usr/bin/env bash
set -Eeuo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
ENV_FILE="${ENV_FILE:-.env}"

COMPOSE_FILE="${COMPOSE_FILE:-deploy/docker-compose.yml}"
[[ -f "$ENV_FILE" ]] || { echo "Missing $ENV_FILE" >&2; exit 2; }
if [[ -z "${COMPOSE_PROJECT_NAME:-}" ]]; then
  COMPOSE_PROJECT_NAME="$(sed -n 's/^COMPOSE_PROJECT_NAME=//p' "$ENV_FILE" | tail -n 1)"
  COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-cfdt-juris}"
fi
# Ensure the least-privilege ingestion/monitor roles exist on upgraded V3.20 volumes.
ENV_FILE="$ENV_FILE" COMPOSE_FILE="$COMPOSE_FILE" COMPOSE_PROJECT_NAME="$COMPOSE_PROJECT_NAME" scripts/ensure_operational_roles.sh
# Always create a verified logical dump before schema changes.
ENV_FILE="$ENV_FILE" COMPOSE_FILE="$COMPOSE_FILE" COMPOSE_PROJECT_NAME="$COMPOSE_PROJECT_NAME" scripts/backup_postgres.sh
docker compose -p "$COMPOSE_PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build migrator
# The one-shot migrator receives the DBA URL; the public API container never receives it.
docker compose -p "$COMPOSE_PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" \
  run --rm migrator python /srv/scripts/db_migrate.py upgrade
