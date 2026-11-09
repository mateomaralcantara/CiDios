"""Acceso a Postgres/Supabase.

Dos tipos de transacción:
- ``user_tx(claims)``: cambia al rol ``authenticated``/``anon`` y fija ``request.jwt.claims`` para que
  las políticas RLS se apliquen exactamente igual que en PostgREST/Supabase.
- ``service_tx()``: conexión privilegiada del backend (workers del HARNESS). Nunca se expone al cliente.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from pgvector.psycopg import register_vector
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import get_settings

_pool: ConnectionPool | None = None


def _configure(conn: Connection) -> None:
    register_vector(conn)


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            get_settings().database_url,
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row, "autocommit": False},
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
