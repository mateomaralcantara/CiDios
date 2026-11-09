#!/usr/bin/env bash
# Recrea la base local de desarrollo/pruebas: shim de Supabase + migraciones.
#
# Con psql instalado:
#   DATABASE_URL=postgresql://postgres:postgres@localhost:54329/cdd scripts/db_reset_local.sh
# Sin psql, usando el contenedor de docker-compose.yml:
#   PSQL="docker compose exec -T db psql" DATABASE_URL=postgresql://postgres:postgres@localhost:54329/cdd scripts/db_reset_local.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
: "${DATABASE_URL:?DATABASE_URL requerido}"
PSQL="${PSQL:-psql}"
ADMIN_URL="${DATABASE_URL%/*}/postgres"
DB_NAME="${DATABASE_URL##*/}"; DB_NAME="${DB_NAME%%\?*}"
$PSQL "$ADMIN_URL" -v ON_ERROR_STOP=1 -q -c "drop database if exists \"$DB_NAME\" with (force)" -c "create database \"$DB_NAME\""
$PSQL "$DATABASE_URL" -v ON_ERROR_STOP=1 -q < "$ROOT/supabase/tests/00_local_supabase_shim.sql"
for f in "$ROOT"/supabase/migrations/*.sql; do
  echo "→ $(basename "$f")"
  $PSQL "$DATABASE_URL" -v ON_ERROR_STOP=1 -q < "$f"
done
echo "Base $DB_NAME lista."
