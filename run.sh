#!/usr/bin/env bash
# Start HSC Companion 2027 (creates the virtual environment on first run).
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "First run: creating .venv and installing dependencies…"
  python3 -m venv .venv
  ./.venv/bin/pip install --upgrade pip >/dev/null
  ./.venv/bin/pip install -r requirements.txt
fi
[ -f .env ] || cp .env.example .env
exec ./.venv/bin/python -m app
