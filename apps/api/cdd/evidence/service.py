"""Evidence Engine: afirmaciones ↔ evidencias ↔ fuentes ↔ perspectivas.

No existe una "puntuación universal de verdad": cada afirmación conserva su categoría epistémica,
el balance de evidencia a favor y en contra, y las notas de consenso e incertidumbre.
"""
from __future__ import annotations

import re
from typing import Any

from psycopg import Connection

CATEGORY_LABELS_ES = {
    "empirical_fact": "Hecho empírico comprobable",
    "historical_document": "Documento o testimonio histórico",
    "scholarly_consensus": "Consenso académico",
    "scientific_hypothesis": "Hipótesis científica",
    "philosophical_argument": "Argumento filosófico",
    "theological_interpretation": "Interpretación teológica",
    "religious_belief": "Creencia o doctrina religiosa",
    "contested": "Afirmación controvertida",
    "uncorroborated": "Afirmación sin corroboración",
    "open_question": "Cuestión abierta",
}

PRECISION_LABELS_ES = {
    "exact_day": "fecha exacta", "exact_year": "año exacto", "approximate_year": "año aproximado",
    "range": "intervalo", "decade": "década", "century": "siglo", "disputed": "datación discutida", "unknown": "desconocida",
}

_CLAIM_COLS = """c.id, c.slug, c.statement, c.asserted_by, c.discipline, c.category::text as category, c.is_event,
  c.date_start, c.date_end, c.date_precision::text as date_precision, c.date_label, c.consensus_note,
  c.insufficient_evidence_note, c.future_research_note, c.review_status::text as review_status, c.content_sha256,
  c.origin, c.generated_by,
  c.topic_id, pe.name as place_name, pe.attributes as place_attrs, se.name as subject_name,
  se.attributes as subject_attrs"""


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _claims_query(where: str) -> str:
    return f"""select {_CLAIM_COLS} from public.claims c
      left join public.entities pe on pe.id = c.place_entity_id
      left join public.entities se on se.id = c.subject_entity_id
      where {where}"""


def evidence_for_claims(conn: Connection, claim_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    if not claim_ids:
        return {}
    rows = conn.execute(
        """select e.id, e.claim_id, e.stance::text as stance, e.exact_fragment, e.locator, e.note, e.verification_status,
                  e.chunk_id, ch.content as chunk_content, d.id as document_id, d.title as document_title, d.slug as document_slug,
                  d.license_code, d.review_status::text as document_review_status, d.doc_kind,
                  r.id as reference_id, r.slug as reference_slug, r.authors as reference_authors, r.title as reference_title,
                  r.container_title as reference_container, r.publisher as reference_publisher, r.year as reference_year,
                  r.edition as reference_edition, r.identifiers as reference_identifiers, r.identifier_check
           from public.evidence_links e
           join public.document_chunks ch on ch.id = e.chunk_id
           join public.documents d on d.id = ch.document_id
           left join public.bibliographic_references r on r.id = e.reference_id
           where e.claim_id = any(%s::uuid[]) order by e.created_at""", (claim_ids,)).fetchall()
    out: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        r = {k: (str(v) if k.endswith("id") and v is not None else v) for k, v in r.items()}
        out.setdefault(r["claim_id"], []).append(r)
    return out


def perspectives_for_claims(conn: Connection, claim_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    if not claim_ids:
        return {}
    rows = conn.execute(
        """select id, claim_id, label, tradition, summary, held_by, evidence_link_ids from public.perspectives
           where claim_id = any(%s::uuid[]) order by created_at""", (claim_ids,)).fetchall()
    out: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        out.setdefault(str(r["claim_id"]), []).append(
            {**r, "id": str(r["id"]), "claim_id": str(r["claim_id"]),
             "evidence_link_ids": [str(x) for x in r["evidence_link_ids"]]})
    return out


def _serialize_claim(r: dict[str, Any]) -> dict[str, Any]:
    out = {k: (str(v) if k in ("id", "topic_id") and v is not None else v) for k, v in r.items()}
    out["category_label"] = CATEGORY_LABELS_ES.get(out["category"], out["category"])
    out["date_precision_label"] = PRECISION_LABELS_ES.get(out["date_precision"], out["date_precision"])
    return out


def get_claims(conn: Connection, claim_ids: list[str], with_evidence: bool = True) -> list[dict[str, Any]]:
    rows = conn.execute(_claims_query("c.id = any(%s::uuid[])") + " order by c.date_start nulls last, c.slug",
                        (claim_ids,)).fetchall()
    claims = [_serialize_claim(r) for r in rows]
    if with_evidence:
        ids = [c["id"] for c in claims]
        ev, ps = evidence_for_claims(conn, ids), perspectives_for_claims(conn, ids)
        for c in claims:
            c["evidence"] = ev.get(c["id"], [])
            c["perspectives"] = ps.get(c["id"], [])
    return claims


def claims_by_topic(conn: Connection, topic_slug: str) -> list[dict[str, Any]]:
    rows = conn.execute(_claims_query("c.topic_id = (select id from public.topics where slug = %s)") +
                        " order by c.date_start nulls last, c.slug", (topic_slug,)).fetchall()
    return get_claims(conn, [str(r["id"]) for r in rows])


def claims_for_chunks(conn: Connection, chunk_ids: list[str]) -> list[str]:
    rows = conn.execute("select distinct claim_id from public.evidence_links where chunk_id = any(%s::uuid[])",
                        (chunk_ids,)).fetchall()
    return [str(r["claim_id"]) for r in rows]


def stance_balance(evidence: list[dict[str, Any]]) -> dict[str, int]:
    bal = {"supports": 0, "challenges": 0, "contextualizes": 0, "qualifies": 0}
    for e in evidence:
        bal[e["stance"]] = bal.get(e["stance"], 0) + 1
    return bal


def verify_evidence_link(e: dict[str, Any]) -> tuple[str, list[str]]:
    """Verificación de una cita: el fragmento debe aparecer literalmente en el texto indexado de la fuente."""
    problems: list[str] = []
    if _norm_ws(e["exact_fragment"]) not in _norm_ws(e["chunk_content"]):
        return "fragment_mismatch", ["El fragmento citado no aparece en la fuente"]
    if e.get("reference_id") is None and e.get("doc_kind") == "editorial_note":
        problems.append("Cita de nota editorial sin referencia bibliográfica externa asociada")
    if e.get("identifier_check") == "unverified_offline":
        problems.append("Identificador de la referencia externa no resuelto en línea en este entorno")
    if e.get("document_review_status") != "reviewed":
        problems.append("Fuente pendiente de revisión por especialista")
    return "fragment_verified", problems


def compare_perspectives(conn: Connection, topic_slug: str) -> dict[str, Any]:
    """Matriz comparativa: afirmación × perspectivas, con balance de evidencia y categoría."""
    claims = claims_by_topic(conn, topic_slug)
    rows = []
    for c in claims:
        if not c["perspectives"] and c["category"] not in ("contested", "open_question"):
            continue
        rows.append({
            "claim_id": c["id"], "statement": c["statement"], "category": c["category"],
            "category_label": c["category_label"], "balance": stance_balance(c["evidence"]),
            "consensus_note": c["consensus_note"], "perspectives": c["perspectives"],
            "challenging_evidence": [e for e in c["evidence"] if e["stance"] == "challenges"],
        })
    return {"topic": topic_slug, "rows": rows,
            "note": "Imparcialidad no implica equivalencia probatoria: cada perspectiva se muestra con su evidencia."}
