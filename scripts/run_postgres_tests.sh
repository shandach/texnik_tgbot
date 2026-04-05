#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed in this environment."
  if [[ -n "${TEST_DATABASE_URL:-}" ]]; then
    echo "Running PostgreSQL integration tests against TEST_DATABASE_URL directly..."
    python -m unittest tests.test_postgres_repository_integration -v
    exit 0
  fi
  echo "Set TEST_DATABASE_URL to an existing PostgreSQL instance and rerun:"
  echo "  TEST_DATABASE_URL=postgresql+psycopg://user:password@host:5432/db python -m unittest tests.test_postgres_repository_integration -v"
  exit 0
fi

cleanup() {
  docker compose --profile postgres-test down -v >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "[1/4] Starting postgres-test container..."
docker compose --profile postgres-test up -d postgres-test

echo "[2/4] Waiting for postgres healthcheck..."
for i in {1..40}; do
  status=$(docker inspect --format='{{json .State.Health.Status}}' "$(docker compose ps -q postgres-test)" 2>/dev/null || echo '"starting"')
  if [[ "$status" == '"healthy"' ]]; then
    echo "Postgres is healthy"
    break
  fi
  sleep 1
  if [[ "$i" -eq 40 ]]; then
    echo "Postgres healthcheck timeout" >&2
    exit 1
  fi
done

echo "[3/4] Applying schema..."
docker compose exec -T postgres-test psql -U texnik -d texnik_test -f /workspace/db/schema.sql >/tmp/postgres_schema.log

echo "[4/4] Running postgres integration tests..."
export TEST_DATABASE_URL="postgresql+psycopg://texnik:texnik@127.0.0.1:55432/texnik_test"
python -m unittest tests.test_postgres_repository_integration -v

echo "PostgreSQL integration tests completed successfully."
