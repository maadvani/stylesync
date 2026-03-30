#!/usr/bin/env bash
# Run API with project venv (avoids conda/global python missing uvicorn).
set -e
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q -r requirements.txt

PORT="${PORT:-8000}"
if command -v lsof >/dev/null 2>&1; then
  if lsof -i ":${PORT}" -sTCP:LISTEN -t >/dev/null 2>&1; then
    if curl -sf "http://127.0.0.1:${PORT}/health" | grep -q '"status"'; then
      echo "Backend already running at http://127.0.0.1:${PORT} (health OK). Not starting another."
      exit 0
    fi
    echo "Port ${PORT} is in use but /health did not respond. Stop the other process or set PORT=8001"
    exit 1
  fi
fi

exec .venv/bin/python -m uvicorn main:app --reload --host 127.0.0.1 --port "${PORT}"
