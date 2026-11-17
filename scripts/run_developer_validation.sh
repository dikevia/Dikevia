#!/usr/bin/env bash
# Reproduce the repository's developer validation locally without touching production.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail() { printf 'ERREUR: %s\n' "$*" >&2; exit 1; }
warn() { printf 'AVERTISSEMENT: %s\n' "$*" >&2; }
step() { printf '\n==> %s\n' "$*"; }
require() { command -v "$1" >/dev/null 2>&1 || fail "Commande requise absente: $1"; }

require python
require bash

if [[ "${REQUIRE_POSTGRES_INTEGRATION:-0}" == "1" ]]; then
  [[ -n "${TEST_DATABASE_ADMIN_URL:-}" ]] || fail "TEST_DATABASE_ADMIN_URL est requis."
  [[ -n "${TEST_DATABASE_URL:-}" ]] || fail "TEST_DATABASE_URL est requis."
  [[ -n "${TEST_PLATFORM_ADMIN_DATABASE_URL:-}" ]] || fail "TEST_PLATFORM_ADMIN_DATABASE_URL est requis."
fi

step "Compilation Python et audit du modèle .env"
python -m compileall -q backend/app scripts
python scripts/audit_env_example.py

step "Qualité statique"
require ruff
ruff check backend/app backend/tests scripts --select E4,E7,E9
require bandit
bandit -q -r backend/app -ll

step "Audit des dépendances"
require pip-audit
pip-audit -r backend/requirements-dev.txt

step "Tests unitaires, contrats et intégration PostgreSQL configurée"
PYTHONPATH=backend python -m pytest -q backend/tests

step "Syntaxe des scripts shell"
bash -n scripts/*.sh deploy/init/*.sh

if [[ -f .env ]]; then
  step "Validation de la configuration Docker Compose"
  require docker
  docker compose --env-file .env -f deploy/docker-compose.yml config --quiet
  if [[ "${BUILD_IMAGES:-0}" == "1" ]]; then
    step "Construction des images (BUILD_IMAGES=1)"
    docker compose --env-file .env -f deploy/docker-compose.yml build api migrator
  fi
else
  warn ".env absent : contrôle Docker Compose ignoré. Créez-le avec: python scripts/prepare_dev_env.py"
fi

if [[ -n "${SMOKE_BASE_URL:-}" ]]; then
  step "Smoke tests HTTP non authentifiés"
  require curl
  base="${SMOKE_BASE_URL%/}"
  curl --fail --silent --show-error "$base/health" >/dev/null
  curl --fail --silent --show-error "$base/ready" >/dev/null
  printf 'Endpoints /health et /ready accessibles.\n'
else
  warn "SMOKE_BASE_URL absent : tests HTTP de service non exécutés."
fi

printf '\nVALIDATION LOCALE TERMINEE. Consultez les avertissements ci-dessus et conservez la sortie complète.\n'
