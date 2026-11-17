#!/usr/bin/env bash
set -Eeuo pipefail
# À planifier par cron/systemd. Le jeton est fourni par l'environnement, jamais écrit sur disque.
: "${JURIS_API_URL:?Définir JURIS_API_URL, ex. https://juris.example.fr}"
: "${JURIS_PLATFORM_ADMIN_TOKEN:?Définir le jeton administrateur plateforme}"
WATCHLIST_FILE="${WATCHLIST_FILE:-scripts/legal_watchlist.example}"
[[ -r "$WATCHLIST_FILE" ]] || { echo "Fichier de veille illisible: $WATCHLIST_FILE" >&2; exit 2; }
TODAY="$(date -u +%F)"
while IFS= read -r query; do
  query="${query%%#*}"
  query="$(printf "%s" "$query" | sed -e "s/^[[:space:]]*//" -e "s/[[:space:]]*$//")"
  [[ -z "$query" ]] && continue
  query_string="$(python3 -c 'import sys,urllib.parse; print(urllib.parse.urlencode({"q":sys.argv[1],"effective_date":sys.argv[2],"limit":10}))' "$query" "$TODAY")"
  curl --fail --silent --show-error --retry 2 --retry-delay 2 \
    --request POST \
    --header "Authorization: Bearer ${JURIS_PLATFORM_ADMIN_TOKEN}" \
    "${JURIS_API_URL%/}/api/v1/platform/legal-corpus/ingest/regulatory?${query_string}"
  printf "\\n"
done < "$WATCHLIST_FILE"
