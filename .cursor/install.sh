#!/usr/bin/env bash
# Idempotent repository bootstrap for Signal Engine (Cursor Cloud Agent).
# Installs system services, Python/Node deps, seeds the database, and builds
# the frontend. Safe to re-run: every step checks before mutating state.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> [1/6] Installing system packages (PostgreSQL 16, Redis 7, python venv)"
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
sudo apt-get install -y -qq postgresql postgresql-contrib redis-server python3.12-venv

echo "==> [2/6] Starting PostgreSQL + Redis (needed for db seed + migrations)"
sudo pg_ctlcluster 16 main start 2>/dev/null || true
sudo redis-server /etc/redis/redis.conf --daemonize yes 2>/dev/null || true
for _ in $(seq 1 30); do sudo -u postgres pg_isready -q && break; sleep 1; done

echo "==> [3/6] Ensuring signal_engine role + database exist"
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='signal_engine'" | grep -q 1 \
  || sudo -u postgres psql -c "CREATE ROLE signal_engine WITH LOGIN SUPERUSER PASSWORD 'signal_engine';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='signal_engine'" | grep -q 1 \
  || sudo -u postgres psql -c "CREATE DATABASE signal_engine OWNER signal_engine;"

echo "==> [4/6] Creating repo-root .env if missing (gitignored — local only)"
if [ ! -f .env ]; then
  cat > .env <<'EOF'
# Local development environment (gitignored — never commit)
APP_ENV=development
APP_DEBUG=true

DATABASE_URL=postgresql+asyncpg://signal_engine:signal_engine@localhost:5432/signal_engine
POSTGRES_USER=signal_engine
POSTGRES_PASSWORD=signal_engine
POSTGRES_DB=signal_engine
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

SIGNAL_STORE=postgres

# Auth/site gate off locally
AUTH_PASSWORD=
SITE_TOTP_SECRET=
EOF
fi

echo "==> [5/6] Backend venv + dependencies + migrations"
cd backend
[ -d .venv ] || python3 -m venv .venv
# shellcheck disable=SC1091
. .venv/bin/activate
python -m pip install --upgrade pip -q
pip install -r requirements.txt
alembic upgrade head
deactivate
cd "$REPO_ROOT"

echo "==> [6/6] Frontend dependencies + production build (proxy mode)"
cd frontend
npm install
# CSP blocks eval in dev; must run a production build with the same-origin proxy.
NEXT_PUBLIC_USE_API_PROXY=true npm run build
cd "$REPO_ROOT"

echo "==> Install complete."
