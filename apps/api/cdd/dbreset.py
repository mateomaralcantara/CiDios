"""Recrea una base local de desarrollo o pruebas (multiplataforma, sin psql).

Aplica el shim local de Supabase y todas las migraciones. NUNCA lo uses contra Supabase.
Uso: python -m cdd.dbreset [postgresql://postgres:postgres@localhost:5432/cdd]
     (por defecto usa CDD_DATABASE_URL)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg
from psycopg import sql

ROOT = Path(os.environ.get("CDD_REPO_ROOT", Path(__file__).resolve().parents[3]))


def reset(database_url: str) -> None:
    base, _, name = database_url.rpartition("/")
    name = name.split("?")[0]
    if not name or name in ("postgres", "template0", "template1"):
        raise SystemExit(f"Nombre de base no válido: {name!r}")
    if "supabase.co" in database_url or "pooler.supabase" in database_url:
        raise SystemExit("cdd.dbreset es solo para bases locales; no lo ejecutes contra Supabase.")
    from .db import check_connection
    check_connection(f"{base}/postgres")
    with psycopg.connect(f"{base}/postgres", autocommit=True) as admin:
        admin.execute(sql.SQL("drop database if exists {} with (force)").format(sql.Identifier(name)))
        admin.execute(sql.SQL("create database {}").format(sql.Identifier(name)))
    files = [ROOT / "supabase" / "tests" / "00_local_supabase_shim.sql",
             *sorted((ROOT / "supabase" / "migrations").glob("*.sql"))]
    with psycopg.connect(database_url, autocommit=True) as conn:
        for f in files:
            print(f"→ {f.name}")
            conn.execute(f.read_text(encoding="utf-8"))
    print(f"Base {name} lista.")


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CDD_DATABASE_URL")
    if not url:
        from .config import get_settings
        url = get_settings().database_url
    from .db import DatabaseUnavailable
    try:
        reset(url)
    except DatabaseUnavailable as e:
        raise SystemExit(f"ERROR: {e}") from None
