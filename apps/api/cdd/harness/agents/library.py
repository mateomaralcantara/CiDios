"""Familia II — Bibliotecario universal (#7): Evidence Acquisition Engine."""
from __future__ import annotations

from typing import Any

from ...config import get_settings
from ...connectors.registry import CONNECTORS
from ...evidence.service import claims_for_chunks
from ...library.embeddings import _norm
from ...library.search import search
from ..context import AgentContext

MIN_TERM_COVERAGE = 0.5      # fracción de términos significativos de la consulta presentes en el fragmento
MIN_SEMANTIC = 0.35          # similitud semántica que basta por sí sola


def term_coverage(query: str, text: str) -> float:
    """Proporción de términos significativos (≥4 letras) de la consulta que aparecen en el texto (por raíz de 5 letras)."""
    terms = {w for w in _norm(query) if len(w) >= 4}
    if not terms:
        return 0.0
    stems = {w[:5] for w in _norm(text)}
    return sum(1 for t in terms if t[:5] in stems) / len(terms)


def claims_in_topic(conn, claim_ids: list[str], topic: str) -> list[str]:
    if not claim_ids:
        return []
    rows = conn.execute("""select c.id from public.claims c join public.topics t on t.id = c.topic_id
                           where c.id = any(%s::uuid[]) and t.slug = %s""", (claim_ids, topic)).fetchall()
    return [str(r["id"]) for r in rows]


def universal_librarian(ctx: AgentContext) -> dict[str, Any]:
    hits: dict[str, dict[str, Any]] = {}
    skipped_injection = irrelevant = 0
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
                cov = term_coverage(q, f"{r['locator']} {r['content']}")
                if cov < MIN_TERM_COVERAGE and r["semantic_score"] < MIN_SEMANTIC:
                    irrelevant += 1          # coincidencia débil: no se usa como evidencia
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
        topic = ctx.task_input.get("topic")
        off_topic = 0
        if topic:  # solo afirmaciones del área que se está investigando
            in_topic = claims_in_topic(conn, claim_ids, topic)
            off_topic = len(claim_ids) - len(in_topic)
            claim_ids = in_topic
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
    if irrelevant:
        ctx.log(f"{irrelevant} fragmentos descartados por baja pertinencia con la consulta", level="info")
    if off_topic:
        ctx.log(f"{off_topic} afirmaciones descartadas por pertenecer a otra área", level="info")
    if skipped_injection:
        ctx.log(f"{skipped_injection} fragmentos excluidos por riesgo de inyección de instrucciones", level="warning")
    empty = [p["query"] for p in per_query if p["hits"] == 0]
    if empty:
        ctx.log(f"Sin resultados para {len(empty)} subconsultas", level="warning", data={"queries": empty})
    return {"chunks": sorted(hits.values(), key=lambda h: -h["score"]), "claim_ids": claim_ids,
            "per_query": per_query, "connector_reports": reports,
            "note": "Los candidatos de conectores son metadatos de descubrimiento, no evidencia."}
