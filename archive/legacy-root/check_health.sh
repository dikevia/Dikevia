#!/usr/bin/env bash
set -Eeuo pipefail
BASE_URL="${1:-http://127.0.0.1:8000}"
printf 'Liveness: '
curl --fail --silent --show-error "$BASE_URL/health"
printf '\nReadiness: '
curl --fail --silent --show-error "$BASE_URL/ready"
printf '\n'
