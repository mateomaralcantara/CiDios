"""HARNESS de bibliografía: cada análisis con sustento y citas claras.

Etapas: COLLECT → RESOLVE → AUDIT → CLASSIFY → FORMAT → BIND → REPORT.
- COLLECT: reúne las fuentes de todas las evidencias verificadas de las afirmaciones.
- RESOLVE: resuelve los DOI en Crossref (metadatos canónicos y avisos de retractación).
- AUDIT: excluye evidencia de obras retractadas y fusiona duplicados (mismo DOI).
- CLASSIFY: nivel de procedencia (experto revisado por pares, revisado por pares, publicado, preprint, editorial, usuario).
- FORMAT: referencias en APA 7 y Chicago autor-fecha.
- BIND: numera las referencias [1], [2]… por orden de primera aparición y asigna una clave a cada evidencia.
- REPORT: métricas de solidez del sustento.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from psycopg import Connection

from ..config import get_settings
from ..connectors.base import TIER_LABEL_ES, clean_doi
from ..connectors.crossref import CrossrefConnector
from .formatting import apa, chicago

STRONG = {"expert_peer_reviewed", "peer_reviewed"}


def run(conn: Connection, claims: list[dict[str, Any]], *, resolve_online: bool | None = None,
        max_resolve: int = 30) -> dict[str, Any]:
    s = get_settings()
    if resolve_online is None:
        resolve_online = "crossref" in s.connectors_enabled
    stages: list[dict[str, Any]] = []

    # COLLECT -----------------------------------------------------------------------------------------
    ref_ids, doc_ids = set(), set()
    for c in claims:
        for e in c["evidence"]:
            if e["verification_status"] == "fragment_verified" or e.get("_verified"):
                (ref_ids.add(e["reference_id"]) if e.get("reference_id") else doc_ids.add(e["document_id"]))
    refs = {str(r["id"]): r for r in conn.execute(
        "select * from public.bibliographic_references where id = any(%s::uuid[])", (list(ref_ids),)).fetchall()}
    docs = {str(d["id"]): d for d in conn.execute(
        """select id, title, authors, published_date, institution, source_tier, doi, provenance, doc_kind
           from public.documents where id = any(%s::uuid[])""", (list(doc_ids),)).fetchall()}
    stages.append({"stage": "COLLECT", "ok": True, "detail": f"{len(refs)} referencias y {len(docs)} documentos citados"})

    # RESOLVE -----------------------------------------------------------------------------------------
    resolved = failed = 0
    if resolve_online:
        cr = CrossrefConnector()
        for r in list(refs.values())[:max_resolve]:
            doi = clean_doi(r.get("doi") or (r.get("identifiers") or {}).get("doi"))
            if not doi or r["identifier_check"] == "resolved":
                continue
            try:
                cand = cr.resolve(doi)
            except Exception:  # noqa: BLE001 — red caída: queda sin resolver, no se inventa
                failed += 1
                continue
            if cand is None:
                conn.execute("update public.bibliographic_references set identifier_check='failed', checked_at=now() where id=%s",
                             (r["id"],))
                r["identifier_check"] = "failed"
                failed += 1
                continue
            conn.execute(
                """update public.bibliographic_references set identifier_check='resolved', checked_at=now(),
                     retraction_checked_at=now(), is_retracted = is_retracted or %s,
                     year=coalesce(year, %s), container_title=coalesce(container_title, %s), doi=coalesce(doi, %s)
                   where id=%s""", (cand.is_retracted, cand.year, cand.venue, doi, r["id"]))
            r.update(identifier_check="resolved", is_retracted=bool(r.get("is_retracted")) or cand.is_retracted,
                     year=r.get("year") or cand.year, container_title=r.get("container_title") or cand.venue, doi=doi)
            resolved += 1
        stages.append({"stage": "RESOLVE", "ok": True, "detail": f"{resolved} DOI resueltos en Crossref, {failed} sin resolver"})
    else:
        stages.append({"stage": "RESOLVE", "ok": True, "detail": "omitido: Crossref desactivado o sin conexión"})

    # AUDIT -------------------------------------------------------------------------------------------
    retracted_refs = {rid for rid, r in refs.items() if r.get("is_retracted")}
    by_doi: dict[str, str] = {}
    alias: dict[str, str] = {}
    for rid, r in refs.items():
        d = clean_doi(r.get("doi"))
        if d and d in by_doi:
            alias[rid] = by_doi[d]
        elif d:
            by_doi[d] = rid
    stages.append({"stage": "AUDIT", "ok": True,
                   "detail": f"{len(retracted_refs)} referencias retractadas excluidas, {len(alias)} duplicados fusionados"})

    # CLASSIFY + FORMAT ------------------------------------------------------------------------------
    def entry_for(e: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        rid = e.get("reference_id")
        if rid:
            rid = alias.get(rid, rid)
            r = refs[rid]
            tier = r.get("tier") or "published"
            ent = {"ref_id": rid, "authors": r["authors"], "year": r.get("year"), "title": r["title"],
                   "container_title": r.get("container_title"), "publisher": r.get("publisher"), "edition": r.get("edition"),
                   "ref_type": r.get("ref_type"), "doi": clean_doi(r.get("doi") or (r.get("identifiers") or {}).get("doi")),
                   "url": r.get("url") or (r.get("identifiers") or {}).get("url"), "tier": tier,
                   "identifier_check": r.get("identifier_check"), "cited_by": r.get("cited_by_count"),
                   "retracted": bool(r.get("is_retracted")), "connector": r.get("source_connector")}
            return f"ref:{rid}", ent
        d = docs[e["document_id"]]
        tier = d.get("source_tier") or ("editorial" if d["doc_kind"] == "editorial_note" else "user")
        year = d.get("published_date") or None
        ent = {"ref_id": None, "document_id": str(d["id"]), "authors": d["authors"], "year": year, "title": d["title"],
               "container_title": d.get("institution"), "publisher": None, "ref_type": "other", "doi": clean_doi(d.get("doi")),
               "url": None, "tier": tier, "identifier_check": "not_applicable", "cited_by": None, "retracted": False}
        return f"doc:{d['id']}", ent

    # BIND ---------------------------------------------------------------------------------------------
    order = sorted(claims, key=lambda c: (c.get("date_start") is None, c.get("date_start") or 0, c["slug"]))
    keys: dict[str, int] = {}
    entries: dict[str, dict[str, Any]] = {}
    evidence_keys: dict[str, int] = {}
    excluded: list[dict[str, Any]] = []
    for c in order:
        for e in c["evidence"]:
            if not (e["verification_status"] == "fragment_verified" or e.get("_verified")):
                continue
            if e.get("reference_id") and alias.get(e["reference_id"], e["reference_id"]) in retracted_refs | {
                    alias.get(x, x) for x in retracted_refs}:
                excluded.append({"evidence_id": e["id"], "claim_id": c["id"], "reason": "obra retractada"})
                continue
            k, ent = entry_for(e)
            if k not in keys:
                keys[k] = len(keys) + 1
                ent["key"] = keys[k]
                ent["tier_label"] = TIER_LABEL_ES.get(ent["tier"], ent["tier"])
                ent["apa"] = apa(ent)
                ent["chicago"] = chicago(ent)
                entries[k] = ent
            evidence_keys[e["id"]] = keys[k]
    stages.append({"stage": "CLASSIFY", "ok": True, "detail": "procedencia asignada a cada referencia"})
    stages.append({"stage": "FORMAT", "ok": True, "detail": f"{len(entries)} referencias en APA 7 y Chicago"})
    stages.append({"stage": "BIND", "ok": True, "detail": f"{len(evidence_keys)} evidencias numeradas"})

    # REPORT -------------------------------------------------------------------------------------------
    excluded_ids = {x["evidence_id"] for x in excluded}
    by_tier: dict[str, int] = {}
    for ent in entries.values():
        by_tier[ent["tier"]] = by_tier.get(ent["tier"], 0) + 1
    strong_claims = expert_claims = editorial_only = counted = 0
    for c in claims:
        tiers = {entries[entry_for(e)[0]]["tier"] for e in c["evidence"]
                 if e["id"] in evidence_keys and e["stance"] == "supports" and e["id"] not in excluded_ids}
        if not tiers:
            continue   # afirmación que queda fuera del paquete (p. ej. solo respaldada por una obra retractada)
        counted += 1
        strong_claims += bool(tiers & STRONG)
        expert_claims += "expert_peer_reviewed" in tiers
        editorial_only += bool(tiers) and tiers <= {"editorial", "user"}
    n = max(counted, 1)
    metrics = {"claims_supported": counted, "references": len(entries), "by_tier": by_tier, "evidence_bound": len(evidence_keys),
               "evidence_excluded_retracted": len(excluded), "doi_resolved": resolved, "doi_unresolved": failed,
               "claims_with_peer_reviewed_support_pct": round(100 * strong_claims / n, 1),
               "claims_with_expert_support_pct": round(100 * expert_claims / n, 1),
               "claims_only_editorial_or_user": editorial_only, "generated_at": datetime.now(UTC).isoformat()}
    stages.append({"stage": "REPORT", "ok": True, "detail": f"{metrics['claims_with_peer_reviewed_support_pct']} % de afirmaciones "
                                                             f"con respaldo revisado por pares"})
    return {"entries": sorted(entries.values(), key=lambda x: x["key"]), "evidence_keys": evidence_keys,
            "excluded_evidence": excluded, "metrics": metrics, "stages": stages}
