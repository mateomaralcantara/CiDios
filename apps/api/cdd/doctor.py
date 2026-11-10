"""Diagnóstico de la configuración (local o Supabase): python -m cdd.doctor

Comprueba variables de entorno, conexión, extensiones, migraciones, tablas, RLS, permisos de los roles
de Supabase, datos iniciales, propietario y verificación de tokens. Sale con código 1 si algo falla.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg

from .config import get_settings, mask_secret
from .db import DatabaseUnavailable, _redact, check_connection
from .migrate import migration_files

TABLES = ['profiles', 'user_roles', 'licenses', 'bibliographic_references', 'documents', 'document_chunks', 'topics',
          'entities', 'entity_relations', 'claims', 'evidence_links', 'perspectives', 'investigations', 'agent_definitions',
          'harness_runs', 'harness_tasks', 'harness_events', 'harness_checkpoints', 'experiences', 'learning_progress',
          'budget_policies', 'cost_ledger', 'claim_reviews']
PRIVATE_TABLES = ['investigations', 'harness_runs', 'cost_ledger', 'learning_progress', 'budget_policies', 'user_roles', 'claim_reviews']


class Report:
    def __init__(self) -> None:
        self.failed = self.warned = 0

    def ok(self, msg: str) -> None:
        print(f"  ✓ {msg}")

    def warn(self, msg: str) -> None:
        self.warned += 1
        print(f"  ⚠ {msg}")

    def fail(self, msg: str) -> None:
        self.failed += 1
        print(f"  ✗ {msg}")

    def check(self, cond: bool, ok: str, bad: str, warn_only: bool = False) -> bool:
        if cond:
            self.ok(ok)
        elif warn_only:
            self.warn(bad)
        else:
            self.fail(bad)
        return cond


def run() -> int:
    s = get_settings()
    r = Report()
    url = s.database_url
    is_supabase = "supabase.co" in url or "supabase.com" in url
    print(f"\nCIENCIA Y DIOS · diagnóstico ({s.env})\n")

    print("Configuración")
    r.ok(f"Base de datos: {_redact(url)}" + (" (Supabase)" if is_supabase else " (local)"))
    if is_supabase and ":6543" in url:
        r.ok("Pooler en modo transacción: se desactivan las sentencias preparadas automáticamente")
    has_auth = bool(s.supabase_jwks_url or s.supabase_jwt_secret)
    if s.env in ("staging", "production"):
        r.check(has_auth, "Verificación de tokens de Supabase configurada",
                "Falta CDD_SUPABASE_JWKS_URL o CDD_SUPABASE_JWT_SECRET: nadie podrá iniciar sesión")
        r.check(not s.dev_auth, "Tokens de desarrollo desactivados", "CDD_DEV_AUTH está activo en un entorno no local")
    else:
        r.check(has_auth or s.dev_auth, "Autenticación disponible (" + ("Supabase" if has_auth else "tokens de desarrollo") + ")",
                "Sin Supabase Auth ni CDD_DEV_AUTH=true: nadie podrá iniciar sesión")
    if s.supabase_jwt_secret:
        r.ok(f"Secreto JWT (HS256): {mask_secret(s.supabase_jwt_secret)}")
    if s.supabase_jwks_url:
        try:
            import httpx
            res = httpx.get(s.supabase_jwks_url, timeout=8)
            keys = res.json().get("keys", []) if res.status_code == 200 else []
            r.check(bool(keys), f"JWKS accesible ({len(keys)} clave(s)) en {s.supabase_jwks_url}",
                    f"JWKS no accesible o vacío ({res.status_code}) en {s.supabase_jwks_url}")
        except Exception as e:  # noqa: BLE001
            r.fail(f"No se pudo leer el JWKS: {type(e).__name__}: {e}")
    if s.gemini_api_key:
        r.ok(f"Gemini configurado: modelo {s.gemini_model}, clave {mask_secret(s.gemini_api_key)} (prueba en vivo: python -m cdd.check_external)")
    else:
        r.warn("Sin CDD_GEMINI_API_KEY: los especialistas con LLM no se usarán (modo determinista)")
    r.ok(f"Repositorios habilitados: {', '.join(s.connectors_enabled) or 'ninguno'}")
    if "openalex" in s.connectors_enabled and not s.openalex_api_key:
        r.warn("Sin CDD_OPENALEX_API_KEY: la dimensión 2 (expertos) puede fallar por el cupo compartido de OpenAlex")
    r.check(bool(s.cors_origins), f"CORS permitido para: {', '.join(s.cors_origins)}", "CDD_CORS_ORIGINS vacío", warn_only=True)

    print("\nBase de datos")
    try:
        check_connection(url)
    except DatabaseUnavailable as e:
        r.fail(str(e))
        return _end(r)
    with psycopg.connect(url, autocommit=True, prepare_threshold=None) as conn:
        q = lambda sql, *a: conn.execute(sql, a).fetchone()  # noqa: E731
        ver, user, sup = q("select current_setting('server_version'), current_user, rolsuper from pg_roles where rolname=current_user")
        r.ok(f"Conectado como {user} a PostgreSQL {ver}" + (" (superusuario)" if sup else ""))
        exts = {x[0] for x in conn.execute("select extname from pg_extension").fetchall()}
        for e in ("vector", "pg_trgm", "unaccent"):
            r.check(e in exts, f"Extensión {e}", f"Falta la extensión {e} (la crean las migraciones; en Supabase: Database → Extensions)")
        r.check(q("select to_regprocedure('auth.uid()') is not null")[0], "auth.uid() disponible",
                "No existe auth.uid(): no es una base de Supabase ni tiene el shim local")
        for role in ("anon", "authenticated", "service_role"):
            exists = q("select count(*) from pg_roles where rolname=%s", role)[0] == 1
            member = exists and q("select pg_has_role(current_user, %s, 'MEMBER')", role)[0]
            r.check(member, f"El usuario de conexión puede actuar como {role}",
                    f"El usuario de conexión no es miembro de {role}: el backend no puede aplicar RLS por usuario")

        if q("select to_regclass('supabase_migrations.schema_migrations') is not null")[0]:
            done = {x[0] for x in conn.execute("select version from supabase_migrations.schema_migrations").fetchall()}
            pending = [f"{v}_{n}" for v, n, _ in migration_files() if v not in done]
            r.check(not pending, f"Migraciones al día ({len(done)})", f"Migraciones pendientes: {', '.join(pending)} → python -m cdd.migrate")
        else:
            r.warn("No hay registro de migraciones (normal en una base local creada con cdd.dbreset)")
        present = {x[0] for x in conn.execute("select tablename from pg_tables where schemaname='public'").fetchall()}
        missing = [t for t in TABLES if t not in present]
        if not r.check(not missing, f"Las {len(TABLES)} tablas existen", f"Faltan tablas: {', '.join(missing)} → python -m cdd.migrate"):
            return _end(r)
        rls = conn.execute("""select relname, relrowsecurity, relforcerowsecurity from pg_class
                              where relnamespace='public'::regnamespace and relname = any(%s)""", (TABLES,)).fetchall()
        no_rls = [n for n, on, _ in rls if not on]
        forced = [n for n, _, f in rls if f]
        r.check(not no_rls, "RLS activado en todas las tablas", f"RLS desactivado en: {', '.join(no_rls)}")
        r.check(not forced, "Sin FORCE RLS (el backend, dueño de las tablas, puede escribir)",
                f"FORCE RLS activo en {', '.join(forced)}: aplica la migración 20261110000005 (python -m cdd.migrate)")
        nopol = [t for t in TABLES if q("select count(*) from pg_policies where schemaname='public' and tablename=%s", t)[0] == 0]
        r.check(not nopol, "Todas las tablas tienen políticas", f"Tablas sin políticas: {', '.join(nopol)}")

        # Prueba real de aislamiento: como visitante no se debe poder leer ninguna tabla privada
        leaks = []
        for t in PRIVATE_TABLES:
            try:
                with conn.transaction():
                    conn.execute("set local role anon")
                    conn.execute(f"select 1 from public.{t} limit 1")
                    leaks.append(t)
            except psycopg.errors.InsufficientPrivilege:
                pass
        r.check(not leaks, "Un visitante no puede leer tablas privadas", f"¡Un visitante puede leer {', '.join(leaks)}!")
        with conn.transaction():
            conn.execute("set local role anon")
            public_claims = conn.execute("select count(*) from public.claims").fetchone()[0]
        r.check(public_claims > 0, f"Un visitante puede leer el catálogo público ({public_claims} afirmaciones)",
                "El catálogo público está vacío para visitantes → python -m cdd.seed", warn_only=True)

        print("\nDatos")
        n_agents = q("select count(*) from public.agent_definitions")[0]
        n_oper = q("select count(*) from public.agent_definitions where status='operational' and enabled")[0]
        r.check(n_agents == 40, f"40 agentes registrados ({n_oper} operativos habilitados)", f"{n_agents}/40 agentes → python -m cdd.seed")
        r.check(q("select count(*) from public.topics")[0] == 20, "20 áreas de la enciclopedia", "Faltan áreas → python -m cdd.seed")
        r.check(q("select count(*) from public.budget_policies")[0] > 0, "Políticas de presupuesto", "Sin políticas → python -m cdd.seed")
        owners = q("select count(*) from public.user_roles where role='owner'")[0]
        r.check(owners > 0, f"Propietario asignado ({owners})",
                "No hay ningún propietario: regístrate en la web y ejecuta  python -m cdd.make_owner tu@correo", warn_only=True)
        dev = q("select count(*) from auth.users where email like '%%@cienciaydios.local'")[0]
        if dev and (is_supabase or s.env in ("staging", "production")):
            r.warn(f"Hay {dev} usuario(s) de desarrollo en esta base")
    return _end(r)


def _end(r: Report) -> int:
    print()
    if r.failed:
        print(f"Resultado: {r.failed} error(es), {r.warned} aviso(s). Revisa las líneas con ✗.")
        return 1
    print("Resultado: todo correcto" + (f" ({r.warned} aviso(s))" if r.warned else "") + ".")
    return 0


if __name__ == "__main__":
    os.chdir(Path.cwd())
    sys.exit(run())
