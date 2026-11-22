#!/usr/bin/env bash
set -Eeuo pipefail

echo "Starting Keycloak in single-instance local-cache mode."
/opt/keycloak/bin/kc.sh "$@" &
KC_PID=$!
KCADM_CONFIG=/tmp/kcadm-dikevia.config
KC_LOCAL_URL="http://127.0.0.1:${KC_HTTP_PORT:-10000}"

shutdown() {
  kill "$KC_PID" 2>/dev/null || true
  wait "$KC_PID" 2>/dev/null || true
}
trap shutdown TERM INT

# The realm is already provisioned in Neon, so --import-realm cannot update it.
# Apply the persistent mobile SSO policy to the live realm through Keycloak's
# local Admin CLI, using only the bootstrap administrator credentials held by
# Render. Never expose these credentials to the API or browser.
if [[ -n "${KC_BOOTSTRAP_ADMIN_USERNAME:-}" && -n "${KC_BOOTSTRAP_ADMIN_PASSWORD:-}" ]]; then
  ready=0
  for attempt in $(seq 1 60); do
    if ! kill -0 "$KC_PID" 2>/dev/null; then
      echo "Keycloak exited before becoming ready." >&2
      wait "$KC_PID"
      exit $?
    fi
    if (echo >"/dev/tcp/127.0.0.1/${KC_HTTP_PORT:-10000}") 2>/dev/null; then
      if /opt/keycloak/bin/kcadm.sh config credentials \
        --server "$KC_LOCAL_URL" --realm master \
        --user "$KC_BOOTSTRAP_ADMIN_USERNAME" \
        --password "$KC_BOOTSTRAP_ADMIN_PASSWORD" \
        --config "$KCADM_CONFIG" >/dev/null 2>&1; then
        ready=1
        break
      fi
    fi
    sleep 3
  done

  if [[ "$ready" == "1" ]]; then
    if /opt/keycloak/bin/kcadm.sh update realms/cfdt \
      -s ssoSessionIdleTimeout=604800 \
      -s ssoSessionMaxLifespan=2592000 \
      --config "$KCADM_CONFIG"; then
      echo "Applied Dikévia SSO policy: 7-day idle timeout, 30-day maximum lifespan."
    else
      echo "WARNING: unable to update the existing cfdt realm SSO policy; existing values remain in effect." >&2
    fi
  else
    echo "WARNING: Keycloak admin bootstrap credentials could not authenticate; existing realm SSO policy was not changed." >&2
  fi
else
  echo "WARNING: Keycloak bootstrap admin credentials are unavailable; existing realm SSO policy was not changed." >&2
fi

wait "$KC_PID"
