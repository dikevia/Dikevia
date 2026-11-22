#!/usr/bin/env bash
set -Eeuo pipefail

# Logical PostgreSQL backup from the Compose database service.
# Production requires age encryption; keep the private key off-host.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
ENV_FILE="${ENV_FILE:-.env}"
COMPOSE_FILE="${COMPOSE_FILE:-deploy/docker-compose.yml}"

BACKUP_DIR="${BACKUP_DIR:-./backups}"
[[ -f "$ENV_FILE" ]] || { echo "Missing $ENV_FILE (copy deploy/.env.example to .env)." >&2; exit 2; }
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
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$BACKUP_DIR/cfdt_juris_${STAMP}.dump"
TMP="${OUT}.partial"
trap 'rm -f "$TMP" "${OUT}.age.partial"' EXIT

APP_ENV_VALUE="$(sed -n 's/^APP_ENV=//p' "$ENV_FILE" | tail -n 1)"
AGE_RECIPIENT="$(sed -n 's/^BACKUP_AGE_RECIPIENT=//p' "$ENV_FILE" | tail -n 1)"
if [[ "$APP_ENV_VALUE" == "production" || "$APP_ENV_VALUE" == "staging" ]]; then
  [[ -n "$AGE_RECIPIENT" ]] || { echo "BACKUP_AGE_RECIPIENT obligatoire en production/recette." >&2; exit 2; }
  command -v age >/dev/null 2>&1 || { echo "age doit être installé sur l'hôte pour chiffrer les sauvegardes." >&2; exit 2; }
fi

docker compose -p "$COMPOSE_PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
  pg_dump -U cfdt_migration -d cfdt_juris -Fc --no-owner --no-acl > "$TMP"
test -s "$TMP"
if [[ -n "$AGE_RECIPIENT" ]]; then
  age -r "$AGE_RECIPIENT" -o "${OUT}.age.partial" "$TMP"
  test -s "${OUT}.age.partial"
  mv "${OUT}.age.partial" "${OUT}.age"
  chmod 600 "${OUT}.age"
  sha256sum "${OUT}.age" > "${OUT}.age.sha256"
  chmod 600 "${OUT}.age.sha256"
  rm -f "$TMP"
  echo "Encrypted backup created: ${OUT}.age"
else
  mv "$TMP" "$OUT"
  chmod 600 "$OUT"
  sha256sum "$OUT" > "${OUT}.sha256"
  chmod 600 "${OUT}.sha256"
  echo "WARNING: unencrypted development backup created: $OUT" >&2
fi
echo "Copiez la sauvegarde chiffrée vers un stockage hors serveur et testez régulièrement sa restauration."
