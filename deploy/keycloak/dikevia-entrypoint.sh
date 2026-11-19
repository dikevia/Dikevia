#!/usr/bin/env bash
set -Eeuo pipefail

echo "Starting Keycloak in single-instance local-cache mode; the beta administrator is already provisioned."

/opt/keycloak/bin/kc.sh "$@" &
keycloak_pid=$!
trap 'kill -TERM "$keycloak_pid" 2>/dev/null || true' TERM INT

sync_dikevia_realm_branding() {
  local port="${KC_HTTP_PORT:-10000}"
  local host_header="${KC_HOSTNAME:-localhost}"
  local status=""
  local ready=0
  local attempt
  local temp_home

  host_header="${host_header#https://}"
  host_header="${host_header#http://}"
  host_header="${host_header%%/*}"

  for ((attempt = 1; attempt <= 90; attempt++)); do
    status=""
    if { exec 3<>"/dev/tcp/127.0.0.1/${port}"; } 2>/dev/null; then
      printf 'GET /health/ready HTTP/1.0\r\nHost: %s\r\nConnection: close\r\n\r\n' "$host_header" >&3
      IFS= read -r status <&3 || true
      exec 3>&- 3<&-
      if [[ "$status" == *" 200 "* ]]; then
        ready=1
        break
      fi
    fi
    if ! kill -0 "$keycloak_pid" 2>/dev/null; then
      echo "Keycloak exited before Dikévia realm branding synchronization." >&2
      return 1
    fi
    sleep 2
  done

  if [[ "$ready" != 1 ]]; then
    echo "WARNING: Dikévia realm branding synchronization skipped: Keycloak readiness timeout." >&2
    return 0
  fi

  if [[ -z "${KC_BOOTSTRAP_ADMIN_USERNAME:-}" || -z "${KC_BOOTSTRAP_ADMIN_PASSWORD:-}" ]]; then
    echo "WARNING: Dikévia realm branding synchronization skipped: bootstrap administrator credentials unavailable." >&2
    return 0
  fi

  temp_home="$(mktemp -d)"
  chmod 700 "$temp_home"
  if KC_CLI_PASSWORD="$KC_BOOTSTRAP_ADMIN_PASSWORD" HOME="$temp_home" \
      /opt/keycloak/bin/kcadm.sh config credentials \
        --server "http://127.0.0.1:${port}" \
        --realm master \
        --user "$KC_BOOTSTRAP_ADMIN_USERNAME" >/dev/null 2>&1 \
    && HOME="$temp_home" /opt/keycloak/bin/kcadm.sh update realms/cfdt \
        -s displayName=Dikévia \
        -s displayNameHtml=Dikévia >/dev/null 2>&1; then
    local client_internal_id
    client_internal_id="$(
      HOME="$temp_home" /opt/keycloak/bin/kcadm.sh get clients -r cfdt \
        --query clientId=cfdt-juris-web --fields id --format csv --noquotes 2>/dev/null | head -n 1
    )"
    if [[ -n "$client_internal_id" ]] && HOME="$temp_home" /opt/keycloak/bin/kcadm.sh \
        update "clients/${client_internal_id}" -r cfdt \
        -s 'name=Dikévia — application web' >/dev/null 2>&1; then
      echo "Keycloak realm and OIDC client display names synchronized to Dikévia."
    else
      echo "WARNING: Keycloak realm display name synchronized, but OIDC client display name could not be updated." >&2
    fi
  else
    echo "WARNING: Keycloak realm display name could not be synchronized; service will continue." >&2
  fi
  rm -rf "$temp_home"
}

sync_dikevia_realm_branding || true
wait "$keycloak_pid"
