"""Acceso a Postgres/Supabase.

Dos tipos de transacción:
- ``user_tx(claims)``: cambia al rol ``authenticated``/``anon`` y fija ``request.jwt.claims`` para que
  las políticas RLS se apliquen exactamente igual que en PostgREST/Supabase.
- ``service_tx()``: conexión privilegiada del backend (workers del HARNESS). Nunca se expone al cliente.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from pgvector.psycopg import register_vector
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import get_settings

_pool: ConnectionPool | None = None


def _configure(conn: Connection) -> None:
    register_vector(conn)


class DatabaseUnavailable(RuntimeError):
    pass


def _redact(url: str) -> str:
    return re.sub(r"//([^:/@]+):[^@]*@", r"//\1:***@", url)


def check_connection(url: str | None = None) -> None:
    """Falla rápido y con un mensaje útil si la base no es accesible (en vez de reintentar en bucle)."""
    url = url or get_settings().database_url
    try:
        with psycopg.connect(url, connect_timeout=5) as conn:
            conn.execute("select 1")
    except psycopg.OperationalError as e:
        lines = [ln.strip() for ln in str(e).splitlines() if ln.strip()]
        msg = next((ln for ln in lines if "FATAL" in ln or "failed" in ln), lines[0] if lines else repr(e))
        msg = msg.split("failed:", 1)[-1].strip() if "connection to server" in msg else msg
        hint = ""
        if "password authentication failed" in str(e):
            hint = ("\n  → Responde un PostgreSQL con otra contraseña. ¿Tienes otro PostgreSQL instalado en ese puerto? "
                    "El docker-compose.yml del proyecto usa el puerto 54329 con usuario/contraseña postgres/postgres.")
        elif "Connection refused" in str(e) or "timeout" in str(e).lower():
            hint = "\n  → No hay ninguna base escuchando. ¿Está Docker Desktop abierto y has ejecutado «docker compose up -d db»?"
        elif "does not exist" in str(e):
            hint = "\n  → La base no existe todavía. Ejecuta «python -m cdd.dbreset» y «python -m cdd.seed --dev-users»."
        raise DatabaseUnavailable(f"No se puede conectar a {_redact(url)}: {msg}{hint}") from None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            get_settings().database_url,
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row, "autocommit": False,
                    # El pooler de Supabase en modo transacción (puerto 6543) no admite sentencias preparadas
                    **({"prepare_threshold": None} if ":6543" in get_settings().database_url else {})},
            configure=_configure,
            open=True,
        )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def service_tx() -> Iterator[Connection]:
    with get_pool().connection() as conn:
        with conn.transaction():
            yield conn


@contextmanager
def user_tx(claims: dict[str, Any] | None) -> Iterator[Connection]:
    """Transacción con RLS. ``claims`` None = visitante anónimo."""
    role = "authenticated" if claims and claims.get("sub") else "anon"
    payload = json.dumps(claims or {"role": "anon"})
    with get_pool().connection() as conn:
        with conn.transaction():
            conn.execute("select set_config('request.jwt.claims', %s, true)", (payload,))
            conn.execute(f"set local role {role}")
            yield conn
