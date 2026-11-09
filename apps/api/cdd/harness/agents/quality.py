"""Familia VI — Validador de estructuras y contratos (#37)."""
from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from ...experience.contracts import ExperienceSpec, KnowledgePacket, packet_hash
from ..context import AgentContext


def validate(packet_raw: dict, spec_raw: dict) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "passed": bool(ok), "detail": detail})

    try:
        packet = KnowledgePacket.model_validate(packet_raw)
        spec = ExperienceSpec.model_validate(spec_raw)
    except ValidationError as e:
        check("schema", False, str(e)[:500])
        return checks
    check("schema", True)
    check("packet_integrity", packet_hash(packet) == packet.sha256 == spec.packet_sha256, "sha256 del paquete")
    ids = {c.id: c for c in packet.claims}
    refs = {e.claim_id for e in spec.events} | {cid for s in spec.stages for cid in s.event_claim_ids} | \
           {cid for s in spec.sections for cid in s.claim_ids} | \
           {q.claim_id for s in spec.stages if s.mission for q in s.mission.questions}
    unknown = sorted(refs - set(ids))
    check("references_only_packet_claims", not unknown, f"desconocidas: {unknown}" if unknown else "")
    altered = [e.claim_id for e in spec.events if e.claim_id in ids and e.narration != ids[e.claim_id].statement]
    check("statements_unaltered", not altered, f"alteradas: {altered}" if altered else "")
    entry_keys = {b.key for b in packet.bibliography}
    unbound = [e.id for c in packet.claims for e in c.evidence if packet.bibliography and e.citation_key not in entry_keys]
    check("citations_bound_to_bibliography", not unbound, f"evidencias sin referencia: {len(unbound)}" if unbound else "")
    check("no_retracted_sources", not any(b.retracted for b in packet.bibliography))
    check("every_claim_has_verified_support", all(any(ev.stance == "supports" and ev.verification == "fragment_verified"
                                                       for ev in c.evidence) for c in packet.claims))
    if spec.modality in ("timeline", "gamified_timeline"):
        check("events_have_dates", all(e.date_label and e.precision for e in spec.events))
        check("dates_match_packet", all(ids[e.claim_id].date and ids[e.claim_id].date.label == e.date_label
                                        for e in spec.events if e.claim_id in ids))
        check("illustrations_have_provenance", all(e.illustration.provenance.license and e.illustration.provenance.notice
                                                   for e in spec.events))
        check("chronological_order", [e.sort_key for e in spec.events] == sorted(e.sort_key for e in spec.events))
    if spec.gamified:
        qs = [q for s in spec.stages if s.mission for q in s.mission.questions]
        check("missions_present", all(s.mission for s in spec.stages))
        check("missions_completable", all(0 <= q.correct_index < len(q.options) and len(set(q.options)) == len(q.options)
                                          for q in qs))
        check("questions_explained", all(q.explanation.strip() for q in qs))
    return checks


def contract_validator(ctx: AgentContext) -> dict[str, Any]:
    ctx.tool("contracts.validate")
    checks = validate(ctx.deps["package"]["knowledge_packet"], ctx.deps["render"]["experience_spec"])
    failed = [c for c in checks if not c["passed"]]
    for f in failed:
        ctx.log(f"QA falló: {f['check']} {f['detail']}", level="error")
    return {"passed": not failed, "checks": checks}
