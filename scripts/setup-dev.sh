#!/usr/bin/env bash
# Bootstrap local development environment
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Copying environment file..."
cp -n "$ROOT/.env.example" "$ROOT/.env" 2>/dev/null || true

echo "==> Starting Docker services..."
docker compose -f "$ROOT/docker-compose.yml" up -d postgres redis

echo "==> Waiting for PostgreSQL..."
until docker compose -f "$ROOT/docker-compose.yml" exec -T postgres pg_isready -U signal_engine; do
  sleep 1
done

echo "==> Setup complete. Run 'docker compose up --build' to start all services."
