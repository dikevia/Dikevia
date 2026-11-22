#!/usr/bin/env bash
set -Eeuo pipefail

echo "Starting Keycloak in single-instance local-cache mode."
exec /opt/keycloak/bin/kc.sh "$@"
