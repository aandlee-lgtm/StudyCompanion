#!/usr/bin/env bash
# Launch the packaged app (headless) exactly as a user would get it, and check it serves pages.
set -euo pipefail
BIN="dist/HSC Companion.app/Contents/MacOS/HSC Companion"
DATA=$(mktemp -d)
HSC_HEADLESS=1 HSC_DATA_DIR="$DATA" "$BIN" > "$DATA/stdout.log" 2>&1 &
PID=$!
trap 'kill $PID 2>/dev/null || true' EXIT
for i in $(seq 1 90); do
  if curl -fsS http://127.0.0.1:8000/api/ping >/dev/null 2>&1; then break; fi
  sleep 1
done
curl -fsS http://127.0.0.1:8000/api/ping
for path in /setup /static/app.css /static/vendor/katex/katex.min.js; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8000$path")
  echo "$path -> $code"
  [ "$code" = "200" ] || { cat "$DATA/stdout.log"; cat "$DATA/hsc_companion.log" 2>/dev/null; exit 1; }
done
test -f "$DATA/hsc_companion.db" && test -f "$DATA/.env"
echo "Smoke test passed: data folder $DATA"
