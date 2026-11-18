#!/usr/bin/env bash
set -Eeuo pipefail

KC_BIN=/opt/keycloak/bin
${KC_BIN}/kc.sh "$@" &
KC_PID=$!

stop_keycloak() {
  kill -TERM "$KC_PID" 2>/dev/null || true
  wait "$KC_PID" 2>/dev/null || true
}
trap stop_keycloak TERM INT

wait_for_admin_api() {
  for ((attempt=1; attempt<=180; attempt++)); do
    if ! kill -0 "$KC_PID" 2>/dev/null; then
      wait "$KC_PID"
      return 1
    fi

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
  echo "Keycloak admin API did not become ready within six minutes." >&2
  return 1
}

if [[ -n "${DIKEVIA_BOOTSTRAP_ADMIN_USERNAME:-}" ||
      -n "${DIKEVIA_BOOTSTRAP_ADMIN_PASSWORD:-}" ||
      -n "${DIKEVIA_BOOTSTRAP_ADMIN_SUBJECT:-}" ]]; then
  : "${KC_BOOTSTRAP_ADMIN_USERNAME:?Missing Keycloak bootstrap administrator username}"
  : "${KC_BOOTSTRAP_ADMIN_PASSWORD:?Missing Keycloak bootstrap administrator password}"
  : "${DIKEVIA_BOOTSTRAP_ADMIN_USERNAME:?Missing Dikévia initial administrator username}"
  : "${DIKEVIA_BOOTSTRAP_ADMIN_PASSWORD:?Missing Dikévia initial administrator password}"
  : "${DIKEVIA_BOOTSTRAP_ADMIN_SUBJECT:?Missing Dikévia initial administrator subject}"

  if ! [[ "$DIKEVIA_BOOTSTRAP_ADMIN_SUBJECT" =~ ^[0-9a-fA-F-]{36}$ ]]; then
    echo "Invalid initial administrator subject UUID." >&2
    exit 1
  fi

  echo "Waiting for Keycloak administrator API..."
  wait_for_admin_api
  echo "Keycloak administrator API is ready; provisioning the beta account."

  existing="$("${KC_BIN}/kcadm.sh" get users -r cfdt \
    -q "username=$DIKEVIA_BOOTSTRAP_ADMIN_USERNAME")"

  if [[ "$existing" != *"$DIKEVIA_BOOTSTRAP_ADMIN_SUBJECT"* ]]; then
    if [[ "$existing" != "[]" && "$existing" == *'"username"'* ]]; then
      echo "A different Keycloak user already uses the configured initial administrator username." >&2
      exit 1
    fi

    if ! "${KC_BIN}/kcadm.sh" create users -r cfdt \
      -s "id=$DIKEVIA_BOOTSTRAP_ADMIN_SUBJECT" \
      -s "username=$DIKEVIA_BOOTSTRAP_ADMIN_USERNAME" \
      -s enabled=true \
      -s emailVerified=true \
      -s "firstName=Dikevia" \
      -s "lastName=Administrateur"; then
      existing="$("${KC_BIN}/kcadm.sh" get users -r cfdt \
        -q "username=$DIKEVIA_BOOTSTRAP_ADMIN_USERNAME")"
      if [[ "$existing" != *"$DIKEVIA_BOOTSTRAP_ADMIN_SUBJECT"* ]]; then
        echo "Could not provision the initial Dikévia administrator." >&2
        exit 1
      fi
    fi

    existing="$("${KC_BIN}/kcadm.sh" get users -r cfdt \
      -q "username=$DIKEVIA_BOOTSTRAP_ADMIN_USERNAME")"
    if [[ "$existing" != *"$DIKEVIA_BOOTSTRAP_ADMIN_SUBJECT"* ]]; then
      echo "Keycloak did not preserve the configured administrator subject." >&2
      exit 1
    fi

    "${KC_BIN}/kcadm.sh" set-password -r cfdt \
      --username "$DIKEVIA_BOOTSTRAP_ADMIN_USERNAME" \
      --new-password "$DIKEVIA_BOOTSTRAP_ADMIN_PASSWORD"
  fi
  echo "Initial Dikévia administrator is provisioned."
fi

wait "$KC_PID"
