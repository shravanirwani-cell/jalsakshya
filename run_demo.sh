#!/usr/bin/env bash
# Starts the JalSakshya backend and frontend for a live demo.
# Run once from the project root: bash run_demo.sh
set -e

cd "$(dirname "$0")"

if [ ! -f backend/data/jalsakshya.db ]; then
  echo "No database found — running data prep and seeding first..."
  (cd backend && ./venv/Scripts/python.exe scripts/prepare_data.py && ./venv/Scripts/python.exe scripts/seed_db.py)
fi

echo "Starting backend on http://localhost:8000 ..."
(cd backend && ./venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000) &
BACKEND_PID=$!

echo "Starting frontend on http://localhost:5173 ..."
(cd frontend && npm run dev) &
FRONTEND_PID=$!

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
