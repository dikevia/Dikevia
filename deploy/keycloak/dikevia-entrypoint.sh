#!/usr/bin/env bash
set -Eeuo pipefail

KCADM_CONFIG=/tmp/kcadm-dikevia.config
KC_LOCAL_URL="http://127.0.0.1:${KC_HTTP_PORT:-10000}"
BOOTSTRAP_CREATED=0

# KC_BOOTSTRAP_ADMIN_* at server startup only works before the master realm
# exists. This deployment already has a master realm, so use Keycloak's
# documented offline recovery command while this single instance is stopped.
if [[ -n "${KC_BOOTSTRAP_ADMIN_USERNAME:-}" && -n "${KC_BOOTSTRAP_ADMIN_PASSWORD:-}" ]]; then
  if /opt/keycloak/bin/kc.sh bootstrap-admin user --optimized \
    --username:env KC_BOOTSTRAP_ADMIN_USERNAME \
    --password:env KC_BOOTSTRAP_ADMIN_PASSWORD \
    --no-prompt; then
    BOOTSTRAP_CREATED=1
    echo "Created a temporary Keycloak recovery administrator for realm maintenance."
  else
    echo "WARNING: Keycloak temporary administrator recovery did not succeed; no realm settings were changed." >&2
  fi
else
  echo "WARNING: Keycloak recovery credentials are unavailable; no realm settings were changed." >&2
fi

echo "Starting Keycloak in single-instance local-cache mode."
/opt/keycloak/bin/kc.sh "$@" &
KC_PID=$!

cleanup() {
  if [[ "$BOOTSTRAP_CREATED" == "1" && -f "$KCADM_CONFIG" ]]; then
    USER_ID=$(/opt/keycloak/bin/kcadm.sh get users -r master \
      -q "username=${KC_BOOTSTRAP_ADMIN_USERNAME}" --fields id,username \
      --config "$KCADM_CONFIG" 2>/dev/null \
      | grep -m1 '"id"' | sed -E 's/.*"id"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/' || true)
    if [[ -n "$USER_ID" ]]; then
      if /opt/keycloak/bin/kcadm.sh delete "users/$USER_ID" -r master --config "$KCADM_CONFIG"; then
        echo "Removed the temporary Keycloak recovery administrator."
      else
        echo "WARNING: temporary Keycloak recovery administrator could not be removed automatically." >&2
      fi
    fi
  fi
  kill "$KC_PID" 2>/dev/null || true
  wait "$KC_PID" 2>/dev/null || true
}
trap cleanup TERM INT

if [[ "$BOOTSTRAP_CREATED" == "1" ]]; then
  ready=0
  for ((attempt=1; attempt<=60; attempt++)); do
    if ! kill -0 "$KC_PID" 2>/dev/null; then
      echo "Keycloak exited before becoming ready." >&2
      wait "$KC_PID"
      exit $?
    fi
    if /opt/keycloak/bin/kcadm.sh config credentials \
      --server "$KC_LOCAL_URL" --realm master \
      --user "$KC_BOOTSTRAP_ADMIN_USERNAME" \
      --password "$KC_BOOTSTRAP_ADMIN_PASSWORD" \
      --config "$KCADM_CONFIG" >/dev/null 2>&1; then
      ready=1
      break
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
    echo "WARNING: temporary recovery administrator could not authenticate; existing realm SSO policy was not changed." >&2
  fi
fi

wait "$KC_PID"
