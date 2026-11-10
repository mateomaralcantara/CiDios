"""Búsqueda textual, semántica e híbrida sobre la biblioteca (respeta RLS)."""
from __future__ import annotations

from typing import Any, Literal

from psycopg import Connection

from .embeddings import embed_query

Mode = Literal["text", "semantic", "hybrid"]


def search(conn: Connection, query: str, k: int = 10, mode: Mode = "hybrid") -> list[dict[str, Any]]:
    vec, model = embed_query(query) if mode != "text" else (None, None)
    rows = conn.execute(
        "select * from public.hybrid_search(%s, %s::vector, %s, %s, %s)", (query, vec, k, mode, model)
    ).fetchall()
    return [
        {**r, "chunk_id": str(r["chunk_id"]), "document_id": str(r["document_id"]),
         "content": r["content"] if not r["injection_risk"] else "[contenido marcado por riesgo de inyección; revisar]"
         } for r in rows
    ]
