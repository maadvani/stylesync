#!/usr/bin/env bash
# Start backend + frontend together (from repo root).
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
echo "Starting backend..."
( cd "$ROOT/backend" && ./run_server.sh ) &
sleep 2
echo "Starting frontend..."
( cd "$ROOT/frontend" && npm run dev ) &
echo "Backend: http://127.0.0.1:8000  |  Frontend: check terminal for Vite URL (often http://localhost:5173)"
wait
