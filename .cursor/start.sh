#!/usr/bin/env bash
# Per-boot startup for Signal Engine: bring up the system daemons that do not
# start automatically. Application processes (API, Celery, frontend) run as
# tmux-backed terminals defined in environment.json. Idempotent.
set -euo pipefail

echo "==> Starting PostgreSQL 16 cluster"
sudo pg_ctlcluster 16 main start 2>/dev/null || true

echo "==> Starting Redis 7"
sudo redis-server /etc/redis/redis.conf --daemonize yes 2>/dev/null || true

echo "==> Waiting for PostgreSQL to accept connections"
for _ in $(seq 1 30); do
  if sudo -u postgres pg_isready -q; then
    echo "PostgreSQL ready."
    break
  fi
  sleep 1
done

if redis-cli ping >/dev/null 2>&1; then
  echo "Redis ready."
fi
