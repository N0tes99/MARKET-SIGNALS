#!/bin/sh
set -e
cd /app
# Glibc arenas explode with ThreadPoolExecutor; Render free is 512MB.
export MALLOC_ARENA_MAX="${MALLOC_ARENA_MAX:-2}"
echo "Running database migrations..."
alembic upgrade head
PORT="${PORT:-8000}"
echo "Starting uvicorn on 0.0.0.0:${PORT}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
