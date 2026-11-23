#!/usr/bin/env bash
set -euo pipefail
for attempt in $(seq 1 60); do
  run_json="$(gh run list --workflow CI --commit "$GITHUB_SHA" --json status,conclusion --jq '.[0]')"
  status="$(jq -r '.status // ""' <<< "$run_json")"
  conclusion="$(jq -r '.conclusion // ""' <<< "$run_json")"
  if [[ "$status" == "completed" && "$conclusion" == "success" ]]; then
    echo "CI passed for $GITHUB_SHA."
    exit 0
  fi
  if [[ "$status" == "completed" ]]; then
    echo "CI failed; staging embedding import blocked." >&2
    exit 1
  fi
  sleep 10
done
echo "CI wait timed out; staging embedding import blocked." >&2
exit 1
