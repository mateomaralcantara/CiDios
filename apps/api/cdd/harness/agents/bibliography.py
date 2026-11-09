"""Agente #12 — Auditor de procedencia: ejecuta el HARNESS de bibliografía sobre las afirmaciones verificadas."""
from __future__ import annotations

from typing import Any

from ...bibliography import harness
from ...evidence.service import get_claims
from ..context import AgentContext


def provenance_auditor(ctx: AgentContext) -> dict[str, Any]:
    ctx.tool("evidence.read")
    ids = ctx.deps["verify"]["verified_claim_ids"]
    with ctx.as_owner() as conn:
        claims = get_claims(conn, ids)
    ctx.tool("bibliography.resolve")
    from ...db import service_tx
    with service_tx() as conn:
        out = harness.run(conn, claims)
    for st in out["stages"]:
        ctx.log(f"Bibliografía · {st['stage']}: {st['detail']}")
    return out
