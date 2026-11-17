#!/usr/bin/env bash
set -Eeuo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
MODE="local"
if [[ "${1:-}" == "--staging" ]]; then MODE="staging"; elif [[ -n "${1:-}" ]]; then echo "Usage: $0 [--staging]" >&2; exit 2; fi
command -v docker >/dev/null || { echo "Docker est requis." >&2; exit 2; }
docker compose version >/dev/null 2>&1 || { echo "Le plugin Docker Compose est requis." >&2; exit 2; }
command -v python3 >/dev/null || { echo "Python 3 est requis pour préparer les secrets." >&2; exit 2; }
if [[ "$MODE" == "staging" ]]; then
  ENV_FILE=".env.staging"
  [[ -f "$ENV_FILE" ]] || python3 scripts/prepare_dev_env.py --staging
  [[ ! -f "$ENV_FILE" ]] || python3 scripts/upgrade_env_file.py --staging
  if grep -q 'example.org' "$ENV_FILE"; then echo "Remplacez les domaines example.org dans .env.staging avant démarrage." >&2; exit 2; fi
  grep -q '^APP_ENV=production$' "$ENV_FILE" || { echo "Le staging doit utiliser APP_ENV=production." >&2; exit 2; }
  PROJECT="$(sed -n 's/^COMPOSE_PROJECT_NAME=//p' "$ENV_FILE" | tail -n 1)"
  PROJECT="${PROJECT:-cfdt-juris-staging}"
  COMPOSE_ARGS=(-f deploy/docker-compose.yml)
  HEALTH_URL="http://127.0.0.1:18000/ready"
else
  ENV_FILE=".env"
  [[ -f "$ENV_FILE" ]] || python3 scripts/prepare_dev_env.py
  [[ ! -f "$ENV_FILE" ]] || python3 scripts/upgrade_env_file.py
  PROJECT="$(sed -n 's/^COMPOSE_PROJECT_NAME=//p' "$ENV_FILE" | tail -n 1)"
  PROJECT="${PROJECT:-cfdt-juris}"
  COMPOSE_ARGS=(-f deploy/docker-compose.yml)
  HEALTH_URL="http://127.0.0.1:8000/ready"
fi
python3 scripts/render_keycloak_config.py --env-file "$ENV_FILE"
if [[ "$MODE" == "staging" ]]; then RUNTIME_ENV_FILE=".env.staging.runtime"; else RUNTIME_ENV_FILE=".env.runtime"; fi
python3 scripts/render_runtime_env.py --source "$ENV_FILE" --output "$RUNTIME_ENV_FILE"
if [[ ! -f deploy/monitoring/alertmanager.yml ]]; then
  cp deploy/monitoring/alertmanager.yml.example deploy/monitoring/alertmanager.yml
  chmod 600 deploy/monitoring/alertmanager.yml
  echo "Configuration Alertmanager copiée : renseignez le SMTP avant d'activer la supervision." >&2
fi
DC=(docker compose -p "$PROJECT" --env-file "$ENV_FILE" "${COMPOSE_ARGS[@]}")
# Start only infrastructure first: schema changes must finish before the API serves traffic.
"${DC[@]}" build api migrator
"${DC[@]}" up -d db keycloak-db keycloak clamav
for _ in $(seq 1 60); do
  if "${DC[@]}" exec -T db pg_isready -U cfdt_migration -d cfdt_juris >/dev/null 2>&1; then break; fi
  sleep 2
done
ENV_FILE="$ENV_FILE" COMPOSE_PROJECT_NAME="$PROJECT" scripts/ensure_operational_roles.sh
"${DC[@]}" run --rm migrator python /srv/scripts/db_migrate.py baseline
ENV_FILE="$ENV_FILE" COMPOSE_PROJECT_NAME="$PROJECT" scripts/upgrade_with_backup.sh
"${DC[@]}" up -d
for _ in $(seq 1 60); do
  if python3 -c 'import sys,urllib.request; urllib.request.urlopen(sys.argv[1], timeout=3)' "$HEALTH_URL" >/dev/null 2>&1; then
    break
  fi
  sleep 5
done
python3 - "$HEALTH_URL" <<'PY'
import sys, urllib.request
try:
    urllib.request.urlopen(sys.argv[1], timeout=5)
except Exception as exc:
    raise SystemExit(f"L'API n'est pas prête : {exc}")
PY
if [[ "$MODE" == "staging" ]]; then KEYCLOAK_URL="http://127.0.0.1:18081"; else KEYCLOAK_URL="http://127.0.0.1:8081"; fi
cat <<EOF

CFDT JURIS démarré en mode ${MODE}.
API : ${HEALTH_URL}
Keycloak : ${KEYCLOAK_URL}
IMPORTANT : configurez un reverse proxy HTTPS, les clés PISTE/Stripe et les sauvegardes avant toute ouverture externe.
EOF
