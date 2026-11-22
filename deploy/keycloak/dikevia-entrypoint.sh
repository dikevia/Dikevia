#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "${KC_RECOVERY_BOOTSTRAP:-0}" == "1" ]]; then
  echo "Attempting one-time Keycloak recovery administrator bootstrap."
  if /opt/keycloak/bin/kc.sh bootstrap-admin user --optimized \
    --username:env KC_BOOTSTRAP_ADMIN_USERNAME \
    --password:env KC_BOOTSTRAP_ADMIN_PASSWORD \
    --no-prompt; then
    echo "Temporary Keycloak recovery administrator bootstrap completed."
  else
    echo "WARNING: Keycloak recovery administrator bootstrap did not complete; continuing with normal startup."
  fi
fi

echo "Starting Keycloak in single-instance local-cache mode."
exec /opt/keycloak/bin/kc.sh "$@"
