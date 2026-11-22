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
if [[ "$ENV_FILE" == ".env.staging" ]]; then
  python3 scripts/upgrade_env_file.py --staging
  RUNTIME_ENV_FILE=".env.staging.runtime"
else
  python3 scripts/upgrade_env_file.py
  RUNTIME_ENV_FILE=".env.runtime"
fi
python3 scripts/render_runtime_env.py --source "$ENV_FILE" --output "$RUNTIME_ENV_FILE"
DC=(docker compose -p "$COMPOSE_PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE")
"${DC[@]}" up -d db
for _ in $(seq 1 60); do
  if "${DC[@]}" exec -T db pg_isready -U cfdt_migration -d cfdt_juris >/dev/null 2>&1; then break; fi
  sleep 2
done
"${DC[@]}" exec -T db bash /docker-entrypoint-initdb.d/02-create-corpus-ingest-role.sh
"${DC[@]}" exec -T db bash /docker-entrypoint-initdb.d/03-create-monitor-role.sh
