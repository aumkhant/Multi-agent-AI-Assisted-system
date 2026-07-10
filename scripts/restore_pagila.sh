#!/usr/bin/env bash
# Restores the Pagila sample database into the docker-compose Postgres service.
# Usage: ./scripts/restore_pagila.sh
set -euo pipefail

SERVICE="postgres"
DB_USER="postgres"
DB_NAME="pagila"
PAGILA_RAW="https://raw.githubusercontent.com/devrimgunduz/pagila/master"

echo "Waiting for postgres to be ready..."
until docker compose exec -T "$SERVICE" pg_isready -U "$DB_USER" >/dev/null 2>&1; do
  sleep 1
done

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

echo "Downloading Pagila schema and data..."
curl -fsSL "$PAGILA_RAW/pagila-schema.sql" -o "$tmp_dir/pagila-schema.sql"
curl -fsSL "$PAGILA_RAW/pagila-data.sql" -o "$tmp_dir/pagila-data.sql"

echo "Restoring schema..."
docker compose exec -T "$SERVICE" psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" < "$tmp_dir/pagila-schema.sql"

echo "Restoring data..."
docker compose exec -T "$SERVICE" psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" < "$tmp_dir/pagila-data.sql"

echo "Pagila restored. Now run: alembic upgrade head"
