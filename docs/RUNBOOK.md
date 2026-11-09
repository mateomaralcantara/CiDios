# Runbook: ejecución, despliegue y operación

## Requisitos
Python 3.11+ (probado con 3.13), Node 22, PostgreSQL 16 con `pgvector`, `pg_trgm`, `unaccent` y `uv` (o pip).

## Desarrollo local (sin Supabase)
```bash
# 1) Base de datos local (shim de Supabase + migraciones)
export DATABASE_URL=postgresql://postgres@localhost:5432/cdd
scripts/db_reset_local.sh

# 2) API + worker
cd apps/api
uv venv && uv pip install -e ".[dev]"
cp ../../.env.example .env        # ajusta CDD_DATABASE_URL
.venv/bin/python -m cdd.seed --dev-users
.venv/bin/uvicorn cdd.main:app --port 8000

# 3) Web
cd ../web && npm ci
cp .env.example .env.local
npm run dev                        # http://localhost:3000 → Entrar → «Propietario» / «Usuario»
```

## Pruebas
```bash
cd apps/api && CDD_TEST_DATABASE_URL=postgresql://postgres@localhost:5432/cdd_test .venv/bin/pytest
cd apps/web && npm run typecheck && npm run build
# Prueba final en navegador real (pila completa en marcha):
cd apps/web && WEB_URL=http://localhost:3000 API_URL=http://localhost:8000 node e2e/final-test.mjs
```

## Supabase (proyecto propio, independiente de ChatBiblia)
1. Crea un proyecto nuevo en Supabase (no reutilices ninguno de ChatBiblia).
2. Activa las extensiones `vector`, `pg_trgm`, `unaccent` (las migraciones las crean si el rol lo permite).
3. Aplica las migraciones: `supabase link --project-ref <ref> && supabase db push` (usa `supabase/migrations/`).
   **No** ejecutes `supabase/tests/00_local_supabase_shim.sql` en Supabase.
4. Carga el catálogo: `CDD_DATABASE_URL=<cadena de conexión del pooler> python -m cdd.seed` (sin `--dev-users`).
5. Asigna el primer propietario desde el editor SQL:
   `insert into public.user_roles (user_id, role) values ('<uuid>', 'owner') on conflict (user_id) do update set role='owner';`
6. API: `CDD_SUPABASE_JWT_SECRET` (proyectos con secreto HS256) o `CDD_SUPABASE_JWKS_URL=https://<ref>.supabase.co/auth/v1/.well-known/jwks.json`.
7. Web: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`; `NEXT_PUBLIC_DEV_AUTH=false`.

## Despliegue
- **Frontend → Vercel**: raíz `apps/web`, comando `npm run build`, variables `NEXT_PUBLIC_*`.
- **API y worker → servicio de procesos prolongados** (Fly.io, Render, Railway, Cloud Run, etc.): `apps/api/Dockerfile`.
  En producción conviene separar la API (`CDD_RUN_WORKER_IN_API=false`) del worker (`python -m cdd.worker`); la cola en
  Postgres admite varios workers (`for update skip locked`).
- **Entornos**: un proyecto de Supabase y un juego de variables por entorno (development, staging, production).
- **Backups**: Supabase PITR o `pg_dump` programado; restauración probada en staging antes de cada versión mayor.

## Operación
- Centro de control: `/admin` (solo propietario): agentes, ejecuciones, costes, presupuestos, calidad, usuarios,
  modelos y conectores, publicaciones.
- Ejecución atascada: si el worker murió, el arrendamiento caduca a los 10 minutos y otra instancia la retoma. Las
  tareas completadas se reutilizan desde su checkpoint.
- Conectores externos: `CDD_CONNECTORS_ENABLED='["openalex","crossref"]'` (requiere salida de red a esos hosts).
