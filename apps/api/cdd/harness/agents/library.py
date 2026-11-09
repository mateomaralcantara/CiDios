"""Familia II — Bibliotecario universal (#7): Evidence Acquisition Engine."""
from __future__ import annotations

from typing import Any

from ...config import get_settings
from ...connectors.registry import CONNECTORS
from ...evidence.service import claims_for_chunks
from ...library.search import search
from ..context import AgentContext


def universal_librarian(ctx: AgentContext) -> dict[str, Any]:
    hits: dict[str, dict[str, Any]] = {}
    skipped_injection = 0
    per_query = []
    with ctx.as_owner() as conn:   # RLS del dueño: nunca recupera documentos privados de terceros
        for q in ctx.task_input["queries"]:
            ctx.tool("library.search")
            res = search(conn, q, k=4, mode="hybrid")
            kept = 0
            for r in res:
                if r["injection_risk"]:
                    skipped_injection += 1
                    continue
                if r["score"] <= 0:
                    continue
                kept += 1
                prev = hits.get(r["chunk_id"])
                if prev is None or r["score"] > prev["score"]:
                    hits[r["chunk_id"]] = {"chunk_id": r["chunk_id"], "document_id": r["document_id"],
                                           "document_title": r["document_title"], "locator": r["locator"],
                                           "score": round(float(r["score"]), 5), "query": q}
            per_query.append({"query": q, "hits": kept})
        ctx.tool("evidence.read")
        claim_ids = claims_for_chunks(conn, list(hits))
    reports = []
    s = get_settings()
    if s.connectors_enabled and ctx.task_input.get("topic"):
        ctx.tool("connectors.query")
        for name in s.connectors_enabled:
            cls = CONNECTORS.get(name)
            if cls:
                rep = cls().search(ctx.task_input["queries"][0], limit=3).as_dict()
                reports.append(rep)
                if not rep["ok"]:
                    ctx.log(f"Conector {name} no disponible: {rep['error']}", level="warning")
    if skipped_injection:
        ctx.log(f"{skipped_injection} fragmentos excluidos por riesgo de inyección de instrucciones", level="warning")
    empty = [p["query"] for p in per_query if p["hits"] == 0]
    if empty:
        ctx.log(f"Sin resultados para {len(empty)} subconsultas", level="warning", data={"queries": empty})
    return {"chunks": sorted(hits.values(), key=lambda h: -h["score"]), "claim_ids": claim_ids,
            "per_query": per_query, "connector_reports": reports,
            "note": "Los candidatos de conectores son metadatos de descubrimiento, no evidencia."}
