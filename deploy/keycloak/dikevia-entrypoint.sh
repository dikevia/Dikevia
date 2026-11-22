#!/usr/bin/env bash
set -Eeuo pipefail

KCADM=/opt/keycloak/bin/kcadm.sh
KCADM_CONFIG=/tmp/kcadm-dikevia-recovery.config
KC_LOCAL_URL="http://127.0.0.1:${KC_HTTP_PORT:-10000}"
KC_TEMP_ADMIN="${KC_BOOTSTRAP_ADMIN_USERNAME:-kc-admin}"
KC_ADMIN_PASSWORD="${KC_BOOTSTRAP_ADMIN_PASSWORD:-}"
KC_PERMANENT_ADMIN="dikevia-ops"

shutdown() {
  kill "$KC_PID" 2>/dev/null || true
  wait "$KC_PID" 2>/dev/null || true
}
trap shutdown TERM INT

run_admin_migration() {
  local ready=0 candidate attempt perm_users perm_id temp_users temp_id realm_json

  rm -f "$KCADM_CONFIG"
  for ((attempt=1; attempt<=60; attempt++)); do
    if ! kill -0 "$KC_PID" 2>/dev/null; then
      echo "Keycloak exited before the admin migration could run." >&2
      return 1
    fi
    if (echo >"/dev/tcp/127.0.0.1/${KC_HTTP_PORT:-10000}") 2>/dev/null; then
      for candidate in "$KC_TEMP_ADMIN" "$KC_PERMANENT_ADMIN"; do
        if KC_CLI_PASSWORD="$KC_ADMIN_PASSWORD" "$KCADM" config credentials \
          --server "$KC_LOCAL_URL" --realm master --user "$candidate" \
          --password "$KC_ADMIN_PASSWORD" --config "$KCADM_CONFIG" >/dev/null 2>&1; then
          ready=1
          break 2
        fi
      done
    fi
    sleep 3
  done

  if [[ "$ready" != "1" ]]; then
    echo "WARNING: no temporary or permanent Keycloak administrator could authenticate; migration skipped." >&2
    return 1
  fi

  perm_users=$("$KCADM" get users -r master -q "username=$KC_PERMANENT_ADMIN" --config "$KCADM_CONFIG") || return 1
  if [[ "$perm_users" =~ \"id\"[[:space:]]*:[[:space:]]*\"([^\"]+)\" ]]; then
    perm_id="${BASH_REMATCH[1]}"
  else
    perm_id=$("$KCADM" create users -r master -s username="$KC_PERMANENT_ADMIN" -s enabled=true -i --config "$KCADM_CONFIG") || return 1
  fi

  "$KCADM" set-password -r master --username "$KC_PERMANENT_ADMIN" --new-password "$KC_ADMIN_PASSWORD" --config "$KCADM_CONFIG" || return 1
  "$KCADM" add-roles -r master --uusername "$KC_PERMANENT_ADMIN" --rolename admin --config "$KCADM_CONFIG" || return 1
  "$KCADM" update realms/cfdt -s ssoSessionIdleTimeout=604800 -s ssoSessionMaxLifespan=2592000 --config "$KCADM_CONFIG" || return 1

  realm_json=$("$KCADM" get realms/cfdt --fields ssoSessionIdleTimeout,ssoSessionMaxLifespan --config "$KCADM_CONFIG") || return 1
  if [[ ! "$realm_json" =~ \"ssoSessionIdleTimeout\"[[:space:]]*:[[:space:]]*604800 ]] || \
     [[ ! "$realm_json" =~ \"ssoSessionMaxLifespan\"[[:space:]]*:[[:space:]]*2592000 ]]; then
    echo "WARNING: cfdt SSO timeout verification failed; temporary administrator retained." >&2
    return 1
  fi

  temp_users=$("$KCADM" get users -r master -q "username=$KC_TEMP_ADMIN" --config "$KCADM_CONFIG") || return 1
  if [[ "$temp_users" =~ \"id\"[[:space:]]*:[[:space:]]*\"([^\"]+)\" ]]; then
    temp_id="${BASH_REMATCH[1]}"
    if [[ "$KC_TEMP_ADMIN" != "$KC_PERMANENT_ADMIN" ]]; then
      "$KCADM" delete "users/$temp_id" -r master --config "$KCADM_CONFIG" || return 1
    fi
  fi

  rm -f "$KCADM_CONFIG"
  echo "Keycloak recovery complete: permanent admin configured, cfdt SSO policy verified (7-day idle / 30-day maximum), temporary admin removed."
}

echo "Starting Keycloak in single-instance local-cache mode."
/opt/keycloak/bin/kc.sh "$@" &
KC_PID=$!

if [[ -n "$KC_ADMIN_PASSWORD" ]]; then
  if ! run_admin_migration; then
    echo "WARNING: Keycloak remains available; the administrative migration still requires attention." >&2
  fi
else
  echo "WARNING: bootstrap admin password is unavailable; administrative migration skipped." >&2
fi

wait "$KC_PID"
