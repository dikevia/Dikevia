#!/usr/bin/env bash
set -Eeuo pipefail

echo "Starting Keycloak in single-instance local-cache mode; the beta administrator is already provisioned."
exec /opt/keycloak/bin/kc.sh "$@"
