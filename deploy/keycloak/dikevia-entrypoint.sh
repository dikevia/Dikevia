#!/usr/bin/env bash
set -Eeuo pipefail

KC_BIN=/opt/keycloak/bin
INSTANCE_ID="${RENDER_INSTANCE_ID:-$(hostname)}"
export KC_CACHE_EMBEDDED_CLUSTER_NAME="dikevia-${INSTANCE_ID}"
export KC_CACHE_EMBEDDED_NODE_NAME="${INSTANCE_ID}"
echo "Keycloak stateless cluster instance: ${INSTANCE_ID}"
${KC_BIN}/kc.sh "$@" &
KC_PID=$!

stop_keycloak() {
  kill -TERM "$KC_PID" 2>/dev/null || true
  wait "$KC_PID" 2>/dev/null || true
}
trap stop_keycloak TERM INT

wait_for_admin_api() {
  # Wait for the HTTP listener without starting a JVM-backed CLI on every poll.
  for ((attempt=1; attempt<=180; attempt++)); do
    if ! kill -0 "$KC_PID" 2>/dev/null; then
      wait "$KC_PID"
      return 1
    fi
    if { exec 3<>/dev/tcp/127.0.0.1/10000; } 2>/dev/null; then
      exec 3>&-
      break
    fi
    sleep 2
  done

  # The listener can accept connections while Keycloak is still bootstrapping.
  for ((attempt=1; attempt<=180; attempt++)); do
    if "${KC_BIN}/kcadm.sh" config credentials \
      --server http://127.0.0.1:10000 \
      --realm master \
      --user "$KC_BOOTSTRAP_ADMIN_USERNAME" \
      --password "$KC_BOOTSTRAP_ADMIN_PASSWORD" \
      >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "Keycloak administrator API did not become ready within six minutes." >&2
  return 1
}

if [[ -n "${DIKEVIA_BOOTSTRAP_ADMIN_USERNAME:-}" ||
      -n "${DIKEVIA_BOOTSTRAP_ADMIN_PASSWORD:-}" ]]; then
  : "${KC_BOOTSTRAP_ADMIN_USERNAME:?Missing Keycloak bootstrap administrator username}"
  : "${KC_BOOTSTRAP_ADMIN_PASSWORD:?Missing Keycloak bootstrap administrator password}"
  : "${DIKEVIA_BOOTSTRAP_ADMIN_USERNAME:?Missing Dikévia initial administrator username}"
  : "${DIKEVIA_BOOTSTRAP_ADMIN_PASSWORD:?Missing Dikévia initial administrator password}"

  echo "Waiting for Keycloak administrator API..."
  wait_for_admin_api
  echo "Keycloak administrator API is ready; provisioning the beta account."

  existing="$("${KC_BIN}/kcadm.sh" get users -r cfdt \
    -q "username=$DIKEVIA_BOOTSTRAP_ADMIN_USERNAME")"

  if [[ "$existing" == "[]" || "$existing" != *'"username"'* ]]; then
    if ! "${KC_BIN}/kcadm.sh" create users -r cfdt \
      -s "username=$DIKEVIA_BOOTSTRAP_ADMIN_USERNAME" \
      -s enabled=true \
      -s "firstName=Dikevia" \
      -s "lastName=Administrateur"; then
      existing="$("${KC_BIN}/kcadm.sh" get users -r cfdt \
        -q "username=$DIKEVIA_BOOTSTRAP_ADMIN_USERNAME")"
      if [[ "$existing" == "[]" || "$existing" != *'"username"'* ]]; then
        echo "Could not provision the initial Dikévia administrator." >&2
        exit 1
      fi
    fi
    existing="$("${KC_BIN}/kcadm.sh" get users -r cfdt \
      -q "username=$DIKEVIA_BOOTSTRAP_ADMIN_USERNAME")"
  fi

  user_id="$(printf '%s\n' "$existing" | sed -nE 's/.*"id"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/p' | head -n 1)"
  if [[ -z "$user_id" ]]; then
    echo "Could not read the generated Keycloak administrator subject." >&2
    exit 1
  fi

  if [[ "$existing" != *"dikeviaBootstrapPasswordInitialized"* ]]; then
    "${KC_BIN}/kcadm.sh" set-password -r cfdt \
      --username "$DIKEVIA_BOOTSTRAP_ADMIN_USERNAME" \
      --new-password "$DIKEVIA_BOOTSTRAP_ADMIN_PASSWORD"
    "${KC_BIN}/kcadm.sh" update "users/$user_id" -r cfdt \
      -s 'attributes.dikeviaBootstrapPasswordInitialized=["true"]'
  fi
  echo "Initial Dikévia administrator is provisioned."
fi

wait "$KC_PID"
