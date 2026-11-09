"""Aplica las migraciones de supabase/migrations a una base (Supabase o local), una sola vez cada una.

Registra lo aplicado en supabase_migrations.schema_migrations, la misma tabla que usa la
Supabase CLI («supabase db push»), así que ambos métodos son intercambiables.

Uso:
  python -m cdd.migrate               # aplica las pendientes (usa CDD_DATABASE_URL)
  python -m cdd.migrate --status      # solo muestra qué está aplicado y qué falta
  python -m cdd.migrate --url "postgresql://..."
  python -m cdd.migrate --bundle      # genera supabase/setup_supabase.sql para el SQL Editor de Supabase
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import psycopg

ROOT = Path(os.environ.get("CDD_REPO_ROOT", Path(__file__).resolve().parents[3]))
MIGRATIONS = ROOT / "supabase" / "migrations"


def migration_files() -> list[tuple[str, str, Path]]:
    out = []
    for f in sorted(MIGRATIONS.glob("*.sql")):
        m = re.match(r"^(\d+)_(.+)\.sql$", f.name)
        if m:
            out.append((m.group(1), m.group(2), f))
    return out


def _ensure_table(conn: psycopg.Connection) -> None:
    conn.execute("create schema if not exists supabase_migrations")
    conn.execute("""create table if not exists supabase_migrations.schema_migrations (
                      version text not null primary key, statements text[], name text)""")


def applied_versions(conn: psycopg.Connection) -> set[str]:
    _ensure_table(conn)
    return {r[0] for r in conn.execute("select version from supabase_migrations.schema_migrations").fetchall()}


def preflight(conn: psycopg.Connection) -> list[str]:
    """Comprueba que la base tiene lo que Supabase proporciona (auth.uid(), roles)."""
    problems = []
    if conn.execute("select to_regprocedure('auth.uid()')").fetchone()[0] is None:
        problems.append("No existe auth.uid(): esta base no es de Supabase. Para una base local usa «python -m cdd.dbreset».")
    roles = {r[0] for r in conn.execute(
        "select rolname from pg_roles where rolname in ('anon','authenticated','service_role')").fetchall()}
    missing = {"anon", "authenticated", "service_role"} - roles
    if missing:
        problems.append(f"Faltan los roles de Supabase: {', '.join(sorted(missing))}.")
    return problems


BUNDLE = ROOT / "supabase" / "setup_supabase.sql"


def bundle_sql() -> str:
    """Un único script para pegar en el SQL Editor de Supabase: todas las migraciones en una transacción,
    registradas en supabase_migrations.schema_migrations para que «cdd.migrate» y «supabase db push» las den por aplicadas."""
    files = migration_files()
    parts = [
        "-- =====================================================================",
        "-- CIENCIA Y DIOS — creación completa de las tablas en Supabase",
        "-- Generado con «python -m cdd.migrate --bundle». No editar a mano.",
        "-- Pegar entero en Supabase → SQL Editor → New query → Run.",
        "-- Todo se ejecuta en una sola transacción: si algo falla, no se crea nada.",
        "-- =====================================================================",
        "begin;",
        "",
        "do $$ begin",
        "  if to_regclass('public.claims') is not null then",
        "    raise exception 'Las tablas de CIENCIA Y DIOS ya existen en esta base. Usa «python -m cdd.migrate» para aplicar solo lo pendiente.';",
        "  end if;",
        "end $$;",
    ]
    for v, n, f in files:
        parts += ["", f"-- ######## {v}_{n} ########", f.read_text(encoding="utf-8").rstrip()]
    parts += ["", "-- ######## registro de migraciones (compatible con Supabase CLI) ########",
              "create schema if not exists supabase_migrations;",
              "create table if not exists supabase_migrations.schema_migrations (version text not null primary key, statements text[], name text);",
              "insert into supabase_migrations.schema_migrations (version, name) values"]
    parts.append(",\n".join(f"  ('{v}', '{n}')" for v, n, _ in files) + "\non conflict (version) do nothing;")
    parts += ["", "commit;", "", "-- Listo. Comprueba en Table Editor que aparecen las 22 tablas.", ""]
    return "\n".join(parts)


def run(url: str, status_only: bool = False) -> int:
    from .db import DatabaseUnavailable, check_connection
    try:
        check_connection(url)
    except DatabaseUnavailable as e:
        print(f"ERROR: {e}")
        return 2
    with psycopg.connect(url, autocommit=True) as conn:
        problems = preflight(conn)
        for p in problems:
            print(f"ERROR: {p}")
        if problems:
            return 2
        done = applied_versions(conn)
        pending = [(v, n, f) for v, n, f in migration_files() if v not in done]
        for v, n, _ in migration_files():
            print(f"  {'✓ aplicada ' if v in done else '· pendiente'}  {v}_{n}")
        if status_only or not pending:
            print("Nada que aplicar." if not pending else f"{len(pending)} pendiente(s).")
            return 0
        for v, n, f in pending:
            sql = f.read_text(encoding="utf-8")
            print(f"→ aplicando {v}_{n} …", flush=True)
            try:
                with conn.transaction():
                    conn.execute(sql)
                    conn.execute("insert into supabase_migrations.schema_migrations (version, name, statements) values (%s,%s,%s)",
                                 (v, n, [sql]))
            except psycopg.Error as e:
                print(f"ERROR en {f.name}: {e}".strip())
                print("La migración se revirtió por completo; corrige el problema y vuelve a ejecutar.")
                return 1
        print(f"Listo: {len(pending)} migración(es) aplicada(s).")
        return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", help="Cadena de conexión (por defecto CDD_DATABASE_URL o .env)")
    ap.add_argument("--status", action="store_true", help="Solo mostrar el estado")
    ap.add_argument("--bundle", action="store_true", help=f"Generar {BUNDLE.relative_to(ROOT)} para el SQL Editor de Supabase")
    a = ap.parse_args()
    if a.bundle:
        BUNDLE.write_text(bundle_sql(), encoding="utf-8")
        print(f"→ {BUNDLE.relative_to(ROOT)} ({BUNDLE.stat().st_size // 1024} KB, {len(migration_files())} migraciones)")
        sys.exit(0)
    url = a.url or os.environ.get("CDD_DATABASE_URL")
    if not url:
        from .config import get_settings
        url = get_settings().database_url
    sys.exit(run(url, a.status))
