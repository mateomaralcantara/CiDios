"""Familia IV — Analista de consensos y desacuerdos (#26) y Verificador de citas (#27).

Incluye el Adversarial Research Engine (búsqueda activa de evidencia contraria), el Epistemic
Verification Engine y el Knowledge Compiler (KnowledgePacket).
"""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from ...db import service_tx
from ...evidence.service import get_claims, stance_balance, verify_evidence_link
from ...experience.contracts import (
    BibRef,
    DateInfo,
    DocumentRef,
    EvidenceItem,
    KnowledgePacket,
    PacketClaim,
    PerspectiveItem,
    Place,
    packet_hash,
)
from ..context import AgentContext, NoEvidence

ERA_BOUNDS = [(-10_000, 0, "Antigüedad (a. e. c.)"), (1, 399, "Siglos I–IV"), (400, 1399, "Antigüedad tardía y Edad Media"),
              (1400, 1799, "Imprenta, Renacimiento y Reforma"), (1800, 3000, "Época contemporánea")]


def _all_claim_ids(ctx: AgentContext) -> list[str]:
    ids: list[str] = []
    for key, out in ctx.deps.items():
        if key.startswith("acquire_"):
            ids += [c for c in out.get("claim_ids", []) if c not in ids]
    return ids


def consensus_analyst(ctx: AgentContext) -> dict[str, Any]:
    ctx.tool("evidence.read")
    if ctx.task_input["mode"] == "analyze":
        ids = _all_claim_ids(ctx)
        with ctx.as_owner() as conn:
            claims = get_claims(conn, ids, with_evidence=False)
            topic = ctx.task_input.get("topic")
            area = conn.execute("select title, content_status from public.topics where slug = %s", (topic,)).fetchone() if topic else None
        if not claims:
            if area:
                msg = (f"No hay evidencia verificada en la biblioteca para esta pregunta. Área detectada: «{area['title']}»"
                       + (" (todavía sin contenido verificado)." if area["content_status"] == "empty" else "."))
            else:
                msg = "No hay evidencia verificada en la biblioteca para esta pregunta, y no se reconoció un área de la enciclopedia."
            raise NoEvidence(msg + " No se genera contenido sin fuentes.", {
                "topic": topic, "area": area["title"] if area else None,
                "suggestions": ["Aporta documentos con derechos de uso en la Biblioteca (o pide a un editor que los revise y publique).",
                                "Reformula la pregunta con términos más concretos.",
                                "Cuando estén activos los conectores y la extracción asistida, se podrán incorporar fuentes externas."]})
        coverage: dict[str, int] = {label: 0 for *_, label in ERA_BOUNDS}
        for c in claims:
            if c["date_start"] is not None:
                for lo, hi, label in ERA_BOUNDS:
                    if lo <= c["date_start"] <= hi:
                        coverage[label] += 1
        gaps = [k for k, v in coverage.items() if v == 0]
        if gaps:
            ctx.log(f"Períodos sin afirmaciones verificables en la biblioteca: {', '.join(gaps)}", level="warning")
        by_cat: dict[str, int] = {}
        for c in claims:
            by_cat[c["category"]] = by_cat.get(c["category"], 0) + 1
        return {"claim_ids": [c["id"] for c in claims], "coverage_by_era": coverage, "gaps": gaps, "by_category": by_cat}

    # cross_examine: contraste adversarial
    ids = ctx.deps["analyze"]["claim_ids"]
    with ctx.as_owner() as conn:
        claims = get_claims(conn, ids)
    examined, uncertainties = [], []
    for c in claims:
        bal = stance_balance(c["evidence"])
        flags = []
        if bal["challenges"]:
            flags.append("evidencia_contraria")
        if c["category"] in ("contested", "open_question", "uncorroborated"):
            flags.append(c["category"])
        if c["date_precision"] in ("disputed", "unknown"):
            flags.append("datacion_incierta")
        if not bal["challenges"] and c["category"] in ("contested",):
            flags.append("controversia_sin_evidencia_contraria_en_biblioteca")
        if c["insufficient_evidence_note"]:
            uncertainties.append(f"{c['subject_name'] or c['slug']}: {c['insufficient_evidence_note']}")
        if c["category"] in ("contested", "open_question"):
            uncertainties.append(f"{c['subject_name'] or c['slug']}: {c['statement']}")
        examined.append({"claim_id": c["id"], "balance": bal, "flags": flags, "perspectives": len(c["perspectives"])})
    one_sided = [e["claim_id"] for e in examined if e["balance"]["challenges"] == 0]
    ctx.log(f"{len(examined)} afirmaciones contrastadas; {len(examined) - len(one_sided)} con evidencia contraria registrada")
    return {"examined": examined, "uncertainties": uncertainties,
            "note": "La ausencia de evidencia contraria en la biblioteca no equivale a ausencia de debate académico."}


def _evidence_item(e: dict[str, Any]) -> EvidenceItem:
    status, notes = verify_evidence_link(e)
    ref = None
    if e["reference_id"]:
        ref = BibRef(id=e["reference_id"], slug=e["reference_slug"], authors=e["reference_authors"], title=e["reference_title"],
                     container_title=e["reference_container"], publisher=e["reference_publisher"], year=e["reference_year"],
                     edition=e["reference_edition"], identifiers=e["reference_identifiers"] or {},
                     identifier_check=e["identifier_check"])
    return EvidenceItem(
        id=e["id"], stance=e["stance"], fragment=e["exact_fragment"], locator=e["locator"],
        document=DocumentRef(id=e["document_id"], title=e["document_title"], slug=e["document_slug"],
                             license_code=e["license_code"], review_status=e["document_review_status"], kind=e["doc_kind"]),
        reference=ref, verification=status, verification_notes=notes)


def citation_verifier(ctx: AgentContext) -> dict[str, Any]:
    ctx.tool("evidence.read")
    if ctx.task_input["mode"] == "verify":
        ids = [e["claim_id"] for e in ctx.deps["cross_examine"]["examined"]]
        with ctx.as_owner() as conn:
            claims = get_claims(conn, ids)
            licenses = {r["code"]: r for r in conn.execute("select * from public.licenses").fetchall()}
        verified, rejected, warnings = [], [], set()
        ctx.tool("evidence.verify")
        with service_tx() as w:
            for c in claims:
                ok_support = 0
                for e in c["evidence"]:
                    status, notes = verify_evidence_link(e)
                    w.execute("update public.evidence_links set verification_status=%s, verified_at=now() where id=%s",
                              (status, e["id"]))
                    warnings.update(notes)
                    lic = licenses.get(e["license_code"])
                    if status == "fragment_verified" and e["stance"] == "supports" and lic and lic["allows_display"]:
                        ok_support += 1
                if ok_support:
                    verified.append(c["id"])
                else:
                    rejected.append({"claim_id": c["id"], "reason": "Sin evidencia de apoyo verificada y publicable"})
        ctx.log(f"Verificadas {len(verified)} afirmaciones; rechazadas {len(rejected)}")
        return {"verified_claim_ids": verified, "rejected": rejected, "warnings": sorted(warnings)}

    # package: Knowledge Compiler
    ver = ctx.deps["verify"]
    with ctx.as_owner() as conn:
        claims = get_claims(conn, ver["verified_claim_ids"])
        run = conn.execute("""select i.prompt, i.intent from public.harness_runs r join public.investigations i
                              on i.id = r.investigation_id where r.id = %s""", (ctx.run_id,)).fetchone()
    pclaims = []
    for c in claims:
        attrs = c["place_attrs"] or {}
        pclaims.append(PacketClaim(
            id=c["id"], slug=c["slug"], statement=c["statement"],
            statement_sha256=hashlib.sha256(c["statement"].encode()).hexdigest(),
            asserted_by=c["asserted_by"], discipline=c["discipline"], category=c["category"],
            category_label=c["category_label"], is_event=c["is_event"],
            date=DateInfo(start=c["date_start"], end=c["date_end"], precision=c["date_precision"],
                          precision_label=c["date_precision_label"], label=c["date_label"]) if c["date_start"] is not None else None,
            place=Place(name=c["place_name"], lat=attrs.get("lat"), lon=attrs.get("lon")) if c["place_name"] else None,
            subject=c["subject_name"], illustration_kind=(c["subject_attrs"] or {}).get("illustration"),
            consensus_note=c["consensus_note"], insufficient_evidence_note=c["insufficient_evidence_note"],
            future_research_note=c["future_research_note"], review_status=c["review_status"],
            evidence=[_evidence_item(e) for e in c["evidence"] if verify_evidence_link(e)[0] == "fragment_verified"],
            perspectives=[PerspectiveItem(label=p["label"], tradition=p["tradition"], summary=p["summary"],
                                          held_by=p["held_by"]) for p in c["perspectives"]]))
    limitations = [
        "Las fuentes de este corpus son notas editoriales del proyecto que resumen bibliografía secundaria; "
        "están pendientes de revisión por especialistas.",
        "Los identificadores de las referencias externas no se han resuelto en línea desde este entorno.",
        "La búsqueda semántica usa un modelo léxico local (hashing), no un modelo neuronal.",
    ] + ver["warnings"]
    packet = KnowledgePacket(
        run_id=ctx.run_id, question=run["prompt"], topic=(run["intent"] or {}).get("topic"),
        generated_at=datetime.now(UTC).isoformat(), claims=pclaims, excluded_claims=ver["rejected"],
        uncertainties=ctx.deps["cross_examine"]["uncertainties"],
        limitations=limitations,
        coverage={"by_era": ctx.deps["analyze"]["coverage_by_era"], "gaps": ctx.deps["analyze"]["gaps"]})
    packet.sha256 = packet_hash(packet)
    return {"knowledge_packet": packet.model_dump()}
