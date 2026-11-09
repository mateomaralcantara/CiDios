#!/usr/bin/env bash
# Recrea la base local de desarrollo/pruebas: shim de Supabase + migraciones.
# Uso: DATABASE_URL=postgresql://postgres@localhost:54329/cdd scripts/db_reset_local.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
: "${DATABASE_URL:?DATABASE_URL requerido}"
ADMIN_URL="${DATABASE_URL%/*}/postgres"
DB_NAME="${DATABASE_URL##*/}"; DB_NAME="${DB_NAME%%\?*}"
psql "$ADMIN_URL" -v ON_ERROR_STOP=1 -q -c "drop database if exists \"$DB_NAME\" with (force)" -c "create database \"$DB_NAME\""
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -q -f "$ROOT/supabase/tests/00_local_supabase_shim.sql"
for f in "$ROOT"/supabase/migrations/*.sql; do
  echo "→ $(basename "$f")"
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -q -f "$f"
done
echo "Base $DB_NAME lista."
