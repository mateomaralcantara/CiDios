"""Incorpora a la biblioteca las obras descubiertas por los conectores (dimensiones 1 y 2).

Solo se almacena el RESUMEN publicado (licencia CITATION-ONLY: se muestran extractos, no el texto completo),
con su procedencia completa. Deduplicación por DOI y por hash de contenido.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from psycopg import Connection

from ..connectors.base import Candidate
from .ingest import DocumentInput, DuplicateDocument, ingest_document

TIER_RANK = {"expert_peer_reviewed": 0, "peer_reviewed": 1, "published": 2, "preprint": 3, "editorial": 4, "user": 5}
MIN_ABSTRACT_CHARS = 200


def upsert_reference(conn: Connection, c: Candidate, tier: str) -> str:
    authors = [a.name for a in c.authors if a.name][:25]
    slug = "ext-" + hashlib.sha1((c.doi or f"{c.source}:{c.raw_id or c.title}").encode()).hexdigest()[:16]
    ids = {k: v for k, v in {"doi": c.doi, "url": c.url, "openalex": c.openalex_id}.items() if v}
    row = conn.execute("select id, tier from public.bibliographic_references where (doi is not null and lower(doi) = lower(%s)) or slug = %s",
                       (c.doi, slug)).fetchone()
    if row:
        if TIER_RANK.get(tier, 9) < TIER_RANK.get(row["tier"], 9):
            conn.execute("update public.bibliographic_references set tier=%s where id=%s", (tier, row["id"]))
        if c.is_retracted:
            conn.execute("update public.bibliographic_references set is_retracted=true where id=%s", (row["id"],))
        return str(row["id"])
    ref_type = {"article": "article", "journal-article": "article", "review": "article", "book": "book",
                "book-chapter": "chapter", "preprint": "article"}.get(c.work_type or "", "other")
    return str(conn.execute(
        """insert into public.bibliographic_references (slug, ref_type, authors, title, container_title, publisher, year, language,
             identifiers, identifier_check, tier, doi, url, openalex_id, venue_type, cited_by_count, is_retracted, source_connector)
           values (%s,%s,%s,%s,%s,%s,%s,%s,%s,'unverified_offline',%s,%s,%s,%s,%s,%s,%s,%s) returning id""",
        (slug, ref_type, authors, c.title[:500], c.venue, (c.extra or {}).get("publisher"), c.year, c.language,
         json.dumps(ids), tier, c.doi, c.url, c.openalex_id, c.venue_type, c.cited_by, c.is_retracted, c.source)).fetchone()["id"])


def ingest_candidate(conn: Connection, c: Candidate, *, run_id: str, dimension: str, tier: str | None = None,
                     expert: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Devuelve {document_id, reference_id, chunk_ids, reused} o None si la obra no tiene resumen utilizable."""
    if c.is_retracted or not c.abstract or len(c.abstract) < MIN_ABSTRACT_CHARS:
        return None
    tier = tier or c.tier
    ref_id = upsert_reference(conn, c, tier)
    existing = None
    if c.doi:
        existing = conn.execute("select id, source_tier from public.documents where doi is not null and lower(doi)=lower(%s)",
                                (c.doi,)).fetchone()
    if existing is None:
        authors = ", ".join(a.name for a in c.authors[:6]) + (" et al." if len(c.authors) > 6 else "")
        full = (c.extra or {}).get("full_text")
        body = (f"# {c.title}\n\n## Datos de la obra\n\n{authors or 'Autoría no indicada'} ({c.year or 's. f.'}). "
                f"{c.venue or ''}{'. DOI: ' + c.doi if c.doi else ''}\n\n## Resumen\n\n{c.abstract}"
                + (f"\n\n{full}" if full else ""))
        license_code = (c.extra or {}).get("full_text_license") if full else "CITATION-ONLY"
        rights = (f"Texto completo de acceso abierto ({c.license}); se reproduce con atribución. Metadatos vía {c.source}."
                  if full else f"Resumen publicado de la obra, almacenado como extracto para cita con atribución. Metadatos vía {c.source}.")
        prov = {"content": "full_text" if full else "abstract", "connector": c.source, "url": c.url, "doi": c.doi, "openalex_id": c.openalex_id, "dimension": dimension,
                "run_id": run_id, "retrieved_at": datetime.now(UTC).isoformat(), "license": c.license,
                "work_type": c.work_type, "venue_type": c.venue_type}
        if expert:
            prov["expert"] = expert
        try:
            res = ingest_document(conn, DocumentInput(
                title=c.title[:300], body=body, doc_kind="connector_record", license_code=license_code or "CITATION-ONLY",
                authors=[a.name for a in c.authors[:25]], institution=c.venue, published_date=str(c.year or ""),
                language=c.language or "en", identifier=c.doi or c.raw_id,
                rights_statement=rights,
                provenance={k: v for k, v in prov.items() if v is not None}, visibility="public", review_status="pending_review",
                cites=[ref_id]), owner_id=None)
            doc_id, reused = res["id"], False
        except DuplicateDocument as e:
            doc_id, reused = e.existing_id, True
        conn.execute("update public.documents set source_tier=%s, doi=coalesce(doi, %s) where id=%s",
                     (tier, c.doi if not reused else None, doc_id))
    else:
        doc_id, reused = str(existing["id"]), True
        if TIER_RANK.get(tier, 9) < TIER_RANK.get(existing["source_tier"], 9):
            conn.execute("update public.documents set source_tier=%s where id=%s", (tier, doc_id))
    chunks = [str(r["id"]) for r in conn.execute(
        "select id from public.document_chunks where document_id=%s and not injection_risk order by ordinal", (doc_id,)).fetchall()]
    return {"document_id": str(doc_id), "reference_id": ref_id, "chunk_ids": chunks, "reused": reused, "tier": tier,
            "title": c.title, "doi": c.doi, "source": c.source}
