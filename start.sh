#!/usr/bin/env bash
set -euo pipefail

echo "[start] Running Alembic migrations..."
alembic upgrade head || { echo "Alembic failed"; exit 1; }

echo "[start] Starting Uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000