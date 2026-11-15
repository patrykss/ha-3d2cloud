#!/usr/bin/env bash
# Moonraker/Klipper timelapse post-upload hook.
# Usage: HA_3D2CLOUD_URL=http://192.168.1.10:8080 \
#        HA_3D2CLOUD_TOKEN='secret' ./upload_timelapse.sh /path/to/timelapse.mp4

set -Eeuo pipefail

VIDEO="${1:-}"
HA_URL="${HA_3D2CLOUD_URL:-http://IP_HA:8080}"
API_TOKEN="${HA_3D2CLOUD_TOKEN:-}"

if [[ -z "$VIDEO" ]]; then
  echo "Usage: $0 /absolute/path/to/timelapse.mp4" >&2
  exit 2
fi
if [[ ! -f "$VIDEO" ]]; then
  echo "File not found: $VIDEO" >&2
  exit 3
fi
if [[ ! -s "$VIDEO" ]]; then
  echo "File is empty: $VIDEO" >&2
  exit 4
fi

CURL_ARGS=(
  --fail
  --silent
  --show-error
  --location
  --connect-timeout 15
  --max-time 7200
  --retry 3
  --retry-delay 5
  --retry-all-errors
  --form "file=@${VIDEO}"
  --write-out "\nHTTP_STATUS:%{http_code}\n"
)
if [[ -n "$API_TOKEN" ]]; then
  CURL_ARGS+=(--header "X-API-Token: ${API_TOKEN}")
fi

RESPONSE="$(curl "${CURL_ARGS[@]}" "${HA_URL%/}/api/upload")"
printf '%s\n' "$RESPONSE"

# Usuwamy źródło wyłącznie po odpowiedzi HTTP 202 i potwierdzeniu accepted=true.
if ! grep -q 'HTTP_STATUS:202' <<<"$RESPONSE"; then
  echo "Upload not accepted; keeping local file: $VIDEO" >&2
  exit 10
fi
if ! grep -q '"accepted"[[:space:]]*:[[:space:]]*true' <<<"$RESPONSE"; then
  echo "Server response did not confirm acceptance; keeping local file: $VIDEO" >&2
  exit 11
fi

rm -- "$VIDEO"
echo "Upload accepted by HA; deleted local file: $VIDEO"
