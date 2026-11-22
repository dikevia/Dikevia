#!/usr/bin/env bash
set -Eeuo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
ENV_FILE="${ENV_FILE:-.env}"

COMPOSE_FILE="${COMPOSE_FILE:-deploy/docker-compose.yml}"
VERSION="${1:-}"
[[ "$VERSION" =~ ^[0-9]{1,3}$ ]] || { echo "Usage: $0 VERSION" >&2; exit 2; }
printf 'Rollback destructif de la migration %s. Tapez ROLLBACK-%s pour continuer : ' "$VERSION" "$VERSION"
read -r CONFIRM
[[ "$CONFIRM" == "ROLLBACK-$VERSION" ]] || { echo "Rollback annulé." >&2; exit 1; }
# Create and checksum a database dump before any destructive down migration.
ENV_FILE="$ENV_FILE" COMPOSE_PROJECT_NAME="$COMPOSE_PROJECT_NAME" COMPOSE_FILE="$COMPOSE_FILE" scripts/backup_postgres.sh
docker compose -p "$COMPOSE_PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build migrator
# The runner refuses unless the exact version is the latest, the down file exists,
# its original up-migration checksum matches, and both confirmations are supplied.
docker compose -p "$COMPOSE_PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" \
  run --rm migrator python /srv/scripts/db_migrate.py rollback \
  --version "$VERSION" --confirm "$VERSION" --allow-data-loss
