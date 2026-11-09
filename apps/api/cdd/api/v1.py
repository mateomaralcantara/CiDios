"""API REST v1."""
from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

from ..auth import Principal, get_principal, issue_dev_token, require_owner, require_user
from ..config import get_settings
from ..connectors.registry import CONNECTORS, PLANNED
from ..db import service_tx, user_tx
from ..evidence.service import claims_by_topic, compare_perspectives, get_claims
from ..experience.contracts import ExperienceSpec
from ..experience.export import to_markdown
from ..harness import engine
from ..harness.states import MAIN_CHAIN
from ..library.ingest import DocumentInput, DuplicateDocument, LicenseBlocked, ingest_document
from ..library.search import search
from ..seed import DEV_USERS

router = APIRouter(prefix="/v1")


def _jsonable(rows: Any) -> Any:
    return json.loads(json.dumps(rows, default=str))


# ------------------------------------------------------------------ sistema y sesión
@router.get("/health")
def health() -> dict[str, Any]:
    with service_tx() as conn:
        conn.execute("select 1")
    return {"status": "ok", "env": get_settings().env, "api_version": "v1"}


class DevTokenIn(BaseModel):
    user: Literal["owner", "user", "user2"]


@router.post("/auth/dev-token")
def dev_token(body: DevTokenIn) -> dict[str, str]:
    s = get_settings()
    if not (s.dev_auth and s.env in ("development", "test")):
        raise HTTPException(404, "No disponible")
    uid, email, role = DEV_USERS[body.user]
    return {"access_token": issue_dev_token(uid, email), "user_id": uid, "email": email, "role": role}


@router.get("/me")
def me(p: Principal = Depends(get_principal)) -> dict[str, Any]:
    return {"user_id": p.user_id, "role": p.role, "email": (p.claims or {}).get("email")}


# ------------------------------------------------------------------ enciclopedia
@router.get("/topics")
def topics(p: Principal = Depends(get_principal)) -> list[dict[str, Any]]:
    with user_tx(p.claims) as conn:
        rows = conn.execute("""select t.slug, t.title, t.summary, t.content_status,
                                 (select count(*) from public.claims c where c.topic_id=t.id) as claims
                               from public.topics t order by sort_order""").fetchall()
    return _jsonable(rows)


@router.get("/topics/{slug}")
def topic_article(slug: str, p: Principal = Depends(get_principal)) -> dict[str, Any]:
    with user_tx(p.claims) as conn:
        t = conn.execute("select * from public.topics where slug=%s", (slug,)).fetchone()
        if not t:
            raise HTTPException(404, "Área no encontrada")
        claims = claims_by_topic(conn, slug)
        docs = conn.execute("""select id, title, slug, license_code, review_status::text, authors, cites
                               from public.documents where id in (select distinct ch.document_id from public.evidence_links e
                               join public.document_chunks ch on ch.id=e.chunk_id join public.claims c on c.id=e.claim_id
                               join public.topics t on t.id=c.topic_id where t.slug=%s)""", (slug,)).fetchall()
        ref_ids = sorted({r for d in docs for r in d["cites"]})
        refs = conn.execute("select * from public.bibliographic_references where id = any(%s::uuid[]) order by authors[1], year",
                            (ref_ids,)).fetchall()
    return _jsonable({"topic": t, "claims": claims, "documents": docs, "bibliography": refs})


@router.get("/topics/{slug}/compare")
def topic_compare(slug: str, p: Principal = Depends(get_principal)) -> dict[str, Any]:
    with user_tx(p.claims) as conn:
        return _jsonable(compare_perspectives(conn, slug))


@router.get("/claims/{claim_id}")
def claim(claim_id: str, p: Principal = Depends(get_principal)) -> dict[str, Any]:
    with user_tx(p.claims) as conn:
        res = get_claims(conn, [claim_id])
    if not res:
        raise HTTPException(404, "Afirmación no encontrada")
    return _jsonable(res[0])


# ------------------------------------------------------------------ biblioteca
@router.get("/library/documents")
def documents(p: Principal = Depends(get_principal)) -> list[dict[str, Any]]:
    with user_tx(p.claims) as conn:
        rows = conn.execute("""select d.id, d.slug, d.title, d.doc_kind, d.authors, d.institution, d.language, d.license_code,
                                 d.visibility::text, d.review_status::text, d.consulted_at, d.provenance, d.owner_id,
                                 (select count(*) from public.document_chunks c where c.document_id=d.id) as chunks
                               from public.documents d order by d.created_at""").fetchall()
    return _jsonable(rows)


@router.get("/library/documents/{doc_id}")
def document(doc_id: str, p: Principal = Depends(get_principal)) -> dict[str, Any]:
    with user_tx(p.claims) as conn:
        d = conn.execute("select * from public.documents where id=%s", (doc_id,)).fetchone()
        if not d:
            raise HTTPException(404, "Documento no encontrado")
        chunks = conn.execute("""select id, ordinal, locator, content, injection_risk, injection_signals
                                 from public.document_chunks where document_id=%s order by ordinal""", (doc_id,)).fetchall()
        refs = conn.execute("select * from public.bibliographic_references where id = any(%s::uuid[])", (d["cites"],)).fetchall()
        lic = conn.execute("select * from public.licenses where code=%s", (d["license_code"],)).fetchone()
    if not lic["allows_full_text"]:
        for c in chunks:
            c["content"] = c["content"][:280] + ("…" if len(c["content"]) > 280 else "")
    return _jsonable({"document": d, "chunks": chunks, "references": refs, "license": lic})


class DocumentIn(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    body: str = Field(min_length=50, max_length=200_000)
    license_code: str = "USER-PRIVATE"
    authors: list[str] = []
    published_date: str | None = None
    language: str = "es"
    rights_statement: str = Field(min_length=5, description="Declaración de derechos del aportante")


@router.post("/library/documents", status_code=201)
def upload_document(body: DocumentIn, p: Principal = Depends(require_user)) -> dict[str, Any]:
    doc = DocumentInput(title=body.title, body=body.body, doc_kind="user_upload", license_code=body.license_code,
                        authors=body.authors, published_date=body.published_date, language=body.language,
                        rights_statement=body.rights_statement,
                        provenance={"origin": "user_upload", "uploaded_by": p.user_id}, visibility="private")
    try:
        with user_tx(p.claims) as conn:   # RLS: solo documentos privados propios para usuarios regulares
            return ingest_document(conn, doc, owner_id=p.user_id)
    except LicenseBlocked as e:
        raise HTTPException(422, str(e)) from e
    except DuplicateDocument as e:
        raise HTTPException(409, "Ya existe un documento con el mismo contenido") from e


@router.get("/library/search")
def library_search(q: str = Query(min_length=2, max_length=500), mode: Literal["text", "semantic", "hybrid"] = "hybrid",
                   k: int = Query(10, ge=1, le=50), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    with user_tx(p.claims) as conn:
        results = search(conn, q, k, mode)
    return _jsonable({"query": q, "mode": mode, "embedding_model": "hashing-lexical-v1", "results": results})


# ------------------------------------------------------------------ investigaciones y HARNESS
class InvestigationIn(BaseModel):
    prompt: str = Field(min_length=10, max_length=4000)
    preferences: dict[str, Any] = {}
    budget_usd: float | None = Field(default=None, ge=0, le=100)
    force_new: bool = False


@router.post("/investigations", status_code=201)
def create_investigation(body: InvestigationIn, p: Principal = Depends(require_user)) -> dict[str, Any]:
    if body.budget_usd is not None and not p.is_owner:
        body.budget_usd = None  # solo el propietario fija presupuestos distintos de la política
    try:
        return engine.create_investigation(p, body.prompt, body.preferences, body.budget_usd, body.force_new)
    except engine.PolicyError as e:
        raise HTTPException(422, str(e)) from e


@router.get("/investigations")
def my_investigations(p: Principal = Depends(require_user)) -> list[dict[str, Any]]:
    with user_tx(p.claims) as conn:
        rows = conn.execute("""select i.id, i.prompt, i.status, i.created_at, i.intent,
                                 r.id as run_id, r.state::text as state, r.spent_usd, r.result
                               from public.investigations i left join public.harness_runs r on r.investigation_id=i.id
                               where i.owner_id = %s order by i.created_at desc limit 100""", (p.user_id,)).fetchall()
    return _jsonable(rows)


def _run_visible(conn, run_id: str) -> dict[str, Any]:
    run = conn.execute("select *, state::text as state from public.harness_runs where id=%s", (run_id,)).fetchone()
    if not run:
        raise HTTPException(404, "Ejecución no encontrada")
    return run


@router.get("/runs/{run_id}")
def run_detail(run_id: str, p: Principal = Depends(require_user)) -> dict[str, Any]:
    with user_tx(p.claims) as conn:
        run = _run_visible(conn, run_id)
        tasks = conn.execute("""select task_key, agent_code, phase::text, depends_on, status::text, attempts, cost_usd,
                                  allowed_tools, agent_version, completion_criteria, error, started_at, finished_at
                                from public.harness_tasks where run_id=%s order by created_at""", (run_id,)).fetchall()
        costs = conn.execute("""select kind, agent_code, provider, model, amount_usd, input_tokens, output_tokens, cache_hit, note,
                                  created_at from public.cost_ledger where run_id=%s order by id""", (run_id,)).fetchall()
        checkpoints = conn.execute("select task_key, state::text, output_sha256, created_at from public.harness_checkpoints "
                                   "where run_id=%s order by created_at", (run_id,)).fetchall()
        inv = conn.execute("select prompt, intent, preferences from public.investigations where id=%s",
                           (run["investigation_id"],)).fetchone()
    return _jsonable({"run": run, "investigation": inv, "tasks": tasks, "costs": costs, "checkpoints": checkpoints,
                      "state_chain": MAIN_CHAIN})


@router.get("/runs/{run_id}/tasks/{task_key}/output")
def task_output(run_id: str, task_key: str, p: Principal = Depends(require_user)) -> dict[str, Any]:
    with user_tx(p.claims) as conn:
        row = conn.execute("select output from public.harness_tasks where run_id=%s and task_key=%s", (run_id, task_key)).fetchone()
    if not row:
        raise HTTPException(404, "Tarea no encontrada")
    return _jsonable(row["output"])


@router.get("/runs/{run_id}/events")
def run_events(run_id: str, after: int = 0, p: Principal = Depends(require_user)) -> list[dict[str, Any]]:
    with user_tx(p.claims) as conn:
        _run_visible(conn, run_id)
        rows = conn.execute("select * from public.harness_events where run_id=%s and id > %s order by id limit 500",
                            (run_id, after)).fetchall()
    return _jsonable(rows)


@router.get("/runs/{run_id}/stream")
async def run_stream(run_id: str, request: Request, p: Principal = Depends(require_user)) -> StreamingResponse:
    with user_tx(p.claims) as conn:
        _run_visible(conn, run_id)

    async def gen():
        last = 0
        idle = 0
        while not await request.is_disconnected() and idle < 600:
            def fetch(last: int = last):
                with user_tx(p.claims) as conn:
                    ev = conn.execute("select * from public.harness_events where run_id=%s and id > %s order by id limit 200",
                                      (run_id, last)).fetchall()
                    st = conn.execute("select state::text as state from public.harness_runs where id=%s", (run_id,)).fetchone()
                return ev, st["state"]
            events, state = await asyncio.to_thread(fetch)
            for e in events:
                last = e["id"]
                yield f"id: {e['id']}\nevent: harness\ndata: {json.dumps(e, default=str)}\n\n"
            yield f"event: state\ndata: {json.dumps({'state': state})}\n\n"
            if state in ("READY", "PUBLISHED", "FAILED", "CANCELLED", "PARTIAL") and not events:
                break
            idle = 0 if events else idle + 1
            await asyncio.sleep(0.7)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


def _owns_run_or_owner(run_id: str, p: Principal) -> None:
    with user_tx(p.claims) as conn:
        run = _run_visible(conn, run_id)
    if str(run["owner_id"]) != p.user_id and not p.is_owner:
        raise HTTPException(403, "No autorizado")


@router.post("/runs/{run_id}/pause")
def pause(run_id: str, p: Principal = Depends(require_user)) -> dict[str, str]:
    _owns_run_or_owner(run_id, p)
    engine.request_pause(run_id)
    return {"status": "pause_requested"}


@router.post("/runs/{run_id}/cancel")
def cancel(run_id: str, p: Principal = Depends(require_user)) -> dict[str, str]:
    _owns_run_or_owner(run_id, p)
    return {"state": engine.request_cancel(run_id)}


@router.post("/runs/{run_id}/resume")
def resume(run_id: str, p: Principal = Depends(require_user)) -> dict[str, str]:
    _owns_run_or_owner(run_id, p)
    try:
        return {"state": engine.resume(run_id)}
    except engine.PolicyError as e:
        raise HTTPException(409, str(e)) from e


@router.post("/runs/{run_id}/approve")
def approve(run_id: str, p: Principal = Depends(require_owner)) -> dict[str, str]:
    try:
        return {"state": engine.approve(run_id, p)}
    except engine.PolicyError as e:
        raise HTTPException(409, str(e)) from e


class BudgetIn(BaseModel):
    budget_usd: Decimal = Field(ge=0, le=1000)


@router.post("/runs/{run_id}/budget")
def run_budget(run_id: str, body: BudgetIn, p: Principal = Depends(require_owner)) -> dict[str, str]:
    engine.set_budget(run_id, body.budget_usd, p)
    return {"budget_usd": str(body.budget_usd)}


@router.post("/runs/{run_id}/publish")
def publish(run_id: str, p: Principal = Depends(require_owner)) -> dict[str, str]:
    try:
        return {"experience_id": engine.publish(run_id, p), "state": "PUBLISHED"}
    except (engine.PolicyError, Exception) as e:  # InvalidTransition incluida
        raise HTTPException(409, str(e)) from e


# ------------------------------------------------------------------ experiencias y progreso
def _experience(conn, exp_id: str) -> dict[str, Any]:
    row = conn.execute("select * from public.experiences where id=%s", (exp_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Experiencia no encontrada")
    return row


@router.get("/experiences/{exp_id}")
def experience(exp_id: str, p: Principal = Depends(get_principal)) -> dict[str, Any]:
    with user_tx(p.claims) as conn:
        return _jsonable(_experience(conn, exp_id))


@router.get("/experiences/{exp_id}/export")
def export(exp_id: str, format: Literal["json", "markdown"] = "json", p: Principal = Depends(get_principal)):
    with user_tx(p.claims) as conn:
        e = _experience(conn, exp_id)
    if format == "markdown":
        return PlainTextResponse(to_markdown(e["knowledge_packet"], e["experience_spec"]), media_type="text/markdown")
    return _jsonable({"knowledge_packet": e["knowledge_packet"], "experience_spec": e["experience_spec"]})


@router.get("/experiences/{exp_id}/progress")
def get_progress(exp_id: str, p: Principal = Depends(require_user)) -> dict[str, Any]:
    with user_tx(p.claims) as conn:
        _experience(conn, exp_id)
        row = conn.execute("select * from public.learning_progress where user_id=%s and experience_id=%s",
                           (p.user_id, exp_id)).fetchone()
    return _jsonable(row or {"completed_missions": [], "answers": {}, "score": 0, "unlocked_stage": 0})


class MissionAttempt(BaseModel):
    mission_id: str
    answers: dict[str, int]


@router.post("/experiences/{exp_id}/missions")
def submit_mission(exp_id: str, body: MissionAttempt, p: Principal = Depends(require_user)) -> dict[str, Any]:
    """Califica en el servidor (el cliente nunca decide su puntuación) y guarda el progreso."""
    with user_tx(p.claims) as conn:
        e = _experience(conn, exp_id)
        spec = ExperienceSpec.model_validate(e["experience_spec"])
        stage = next((s for s in spec.stages if s.mission and s.mission.id == body.mission_id), None)
        if stage is None:
            raise HTTPException(404, "Misión no encontrada")
        prog = conn.execute("select * from public.learning_progress where user_id=%s and experience_id=%s",
                            (p.user_id, exp_id)).fetchone()
        unlocked = prog["unlocked_stage"] if prog else 0
        if stage.index > unlocked:
            raise HTTPException(409, "Etapa aún bloqueada")
        feedback, correct = [], 0
        for q in stage.mission.questions:
            given = body.answers.get(q.id)
            ok = given == q.correct_index
            correct += ok
            feedback.append({"question_id": q.id, "correct": ok, "correct_index": q.correct_index,
                             "explanation": q.explanation, "claim_id": q.claim_id})
        ratio = correct / len(stage.mission.questions)
        passed = ratio >= stage.mission.pass_threshold
        completed = set(prog["completed_missions"]) if prog else set()
        answers = dict(prog["answers"]) if prog else {}
        answers[body.mission_id] = body.answers
        if passed:
            completed.add(body.mission_id)
            unlocked = max(unlocked, min(stage.index + 1, len(spec.stages) - 1))
        score = (prog["score"] if prog else 0) + (correct * 10 if passed and body.mission_id not in (prog["completed_missions"] if prog else []) else 0)
        conn.execute(
            """insert into public.learning_progress (user_id, experience_id, completed_missions, answers, score, unlocked_stage, updated_at)
               values (%s,%s,%s,%s,%s,%s,now()) on conflict (user_id, experience_id) do update set
               completed_missions=excluded.completed_missions, answers=excluded.answers, score=excluded.score,
               unlocked_stage=excluded.unlocked_stage, updated_at=now()""",
            (p.user_id, exp_id, sorted(completed), json.dumps(answers), score, unlocked))
    return {"passed": passed, "correct": correct, "total": len(stage.mission.questions), "feedback": feedback,
            "progress": {"completed_missions": sorted(completed), "score": score, "unlocked_stage": unlocked}}


# ------------------------------------------------------------------ centro de control del propietario
admin = APIRouter(prefix="/v1/admin", dependencies=[Depends(require_owner)])


@admin.get("/overview")
def overview(p: Principal = Depends(require_owner)) -> dict[str, Any]:
    with user_tx(p.claims) as conn:
        q = lambda sql: conn.execute(sql).fetchone()  # noqa: E731
        return _jsonable({
            "runs_by_state": conn.execute("select state::text, count(*) from public.harness_runs group by 1 order by 1").fetchall(),
            "spend": q("""select coalesce(sum(amount_usd) filter (where created_at > now()-interval '1 day'),0) as day,
                                 coalesce(sum(amount_usd) filter (where created_at > now()-interval '1 month'),0) as month,
                                 coalesce(sum(input_tokens+output_tokens),0) as tokens
                          from public.cost_ledger where kind='actual'"""),
            "citations": conn.execute("select verification_status, count(*) from public.evidence_links group by 1").fetchall(),
            "library": q("""select (select count(*) from public.documents) as documents,
                                   (select count(*) from public.document_chunks) as chunks,
                                   (select count(*) from public.document_chunks where injection_risk) as flagged_chunks,
                                   (select count(*) from public.claims) as claims,
                                   (select count(*) from public.bibliographic_references) as references"""),
            "agents": q("""select count(*) filter (where status='operational') as operational,
                                  count(*) filter (where status='registered') as registered,
                                  count(*) filter (where not enabled) as disabled from public.agent_definitions"""),
            "recent_errors": conn.execute("""select run_id, task_key, message, created_at from public.harness_events
                                             where level='error' order by id desc limit 10""").fetchall(),
            "experiences": conn.execute("select status, count(*) from public.experiences group by 1").fetchall(),
        })


@admin.get("/agents")
def admin_agents(p: Principal = Depends(require_owner)) -> list[dict[str, Any]]:
    with user_tx(p.claims) as conn:
        return _jsonable(conn.execute("select * from public.agent_definitions order by number").fetchall())


class AgentPatch(BaseModel):
    enabled: bool | None = None
    unit_cost_usd: Decimal | None = Field(default=None, ge=0, le=100)
    max_cost_per_run_usd: Decimal | None = Field(default=None, ge=0, le=1000)


@admin.patch("/agents/{code}")
def patch_agent(code: str, body: AgentPatch, p: Principal = Depends(require_owner)) -> dict[str, Any]:
    with user_tx(p.claims) as conn:
        a = conn.execute("select * from public.agent_definitions where code=%s", (code,)).fetchone()
        if not a:
            raise HTTPException(404, "Agente no encontrado")
        if body.enabled and a["status"] != "operational":
            raise HTTPException(409, "No se puede habilitar un agente que todavía no está implementado")
        conn.execute("""update public.agent_definitions set enabled=coalesce(%s,enabled),
                          unit_cost_usd=coalesce(%s,unit_cost_usd), max_cost_per_run_usd=coalesce(%s,max_cost_per_run_usd),
                          updated_at=now() where code=%s""",
                     (body.enabled, body.unit_cost_usd, body.max_cost_per_run_usd, code))
        return _jsonable(conn.execute("select * from public.agent_definitions where code=%s", (code,)).fetchone())


@admin.get("/runs")
def admin_runs(p: Principal = Depends(require_owner)) -> list[dict[str, Any]]:
    with user_tx(p.claims) as conn:
        return _jsonable(conn.execute(
            """select r.id, r.state::text, r.owner_id, r.spent_usd, r.estimated_usd, r.budget_usd, r.requires_approval,
                      r.created_at, r.finished_at, r.error, r.result, i.prompt
               from public.harness_runs r join public.investigations i on i.id=r.investigation_id
               order by r.created_at desc limit 200""").fetchall())


@admin.get("/costs")
def admin_costs(p: Principal = Depends(require_owner)) -> dict[str, Any]:
    with user_tx(p.claims) as conn:
        return _jsonable({
            "by_run": conn.execute("""select run_id, sum(amount_usd) filter (where kind='actual') as actual,
                                        sum(amount_usd) filter (where kind='estimate') as estimated,
                                        sum(input_tokens+output_tokens) as tokens, bool_or(cache_hit) as cache_hit
                                      from public.cost_ledger group by run_id order by max(created_at) desc limit 100""").fetchall(),
            "by_agent": conn.execute("""select agent_code, provider, model, sum(amount_usd) as actual, count(*) as calls
                                        from public.cost_ledger where kind='actual' group by 1,2,3 order by 4 desc""").fetchall(),
            "by_user": conn.execute("""select user_id, sum(amount_usd) as actual from public.cost_ledger where kind='actual'
                                       group by 1 order by 2 desc""").fetchall(),
        })


@admin.get("/budgets")
def admin_budgets(p: Principal = Depends(require_owner)) -> list[dict[str, Any]]:
    with user_tx(p.claims) as conn:
        return _jsonable(conn.execute("select * from public.budget_policies order by scope, period").fetchall())


class BudgetPolicyIn(BaseModel):
    scope: Literal["global", "user", "investigation", "agent", "provider"]
    scope_ref: str = "*"
    period: Literal["per_run", "daily", "monthly"]
    limit_usd: Decimal = Field(ge=0, le=100000)
    auto_approve_below_usd: Decimal = Field(default=Decimal("0.50"), ge=0)
    active: bool = True


@admin.put("/budgets")
def upsert_budget(body: BudgetPolicyIn, p: Principal = Depends(require_owner)) -> dict[str, Any]:
    with user_tx(p.claims) as conn:
        row = conn.execute(
            """insert into public.budget_policies (scope, scope_ref, period, limit_usd, auto_approve_below_usd, active)
               values (%s,%s,%s,%s,%s,%s) on conflict (scope, scope_ref, period) do update set limit_usd=excluded.limit_usd,
               auto_approve_below_usd=excluded.auto_approve_below_usd, active=excluded.active returning *""",
            (body.scope, body.scope_ref, body.period, body.limit_usd, body.auto_approve_below_usd, body.active)).fetchone()
    return _jsonable(row)


@admin.get("/users")
def admin_users(p: Principal = Depends(require_owner)) -> list[dict[str, Any]]:
    with user_tx(p.claims) as conn:
        return _jsonable(conn.execute(
            """select pr.id, pr.display_name, coalesce(r.role::text,'user') as role, pr.created_at
               from public.profiles pr left join public.user_roles r on r.user_id=pr.id order by pr.created_at""").fetchall())


class RoleIn(BaseModel):
    role: Literal["owner", "editor", "user"]


@admin.put("/users/{user_id}/role")
def set_role(user_id: str, body: RoleIn, p: Principal = Depends(require_owner)) -> dict[str, str]:
    if user_id == p.user_id and body.role != "owner":
        raise HTTPException(409, "El propietario no puede retirarse su propio rol desde aquí")
    with user_tx(p.claims) as conn:
        conn.execute("""insert into public.user_roles (user_id, role, granted_by) values (%s,%s,%s)
                        on conflict (user_id) do update set role=excluded.role, granted_by=excluded.granted_by, granted_at=now()""",
                     (user_id, body.role, p.user_id))
    return {"user_id": user_id, "role": body.role}


@admin.get("/providers")
def providers(p: Principal = Depends(require_owner)) -> dict[str, Any]:
    from ..config import mask_secret
    s = get_settings()
    return {
        "models": [
            {"provider": "local", "model": "deterministic", "configured": True, "used_by": "agentes operativos actuales"},
            {"provider": "anthropic", "model": s.anthropic_model, "configured": bool(s.anthropic_api_key),
             "key_hint": mask_secret(s.anthropic_api_key), "used_by": "ninguno: integración con proveedores LLM aún no implementada"},
        ],
        "embeddings": {"model": "hashing-lexical-v1", "dim": 384, "neural": False},
        "connectors": [{"name": n, "implemented": True, "enabled": n in s.connectors_enabled} for n in CONNECTORS]
                      + [{"name": n, "implemented": False, "enabled": False} for n in PLANNED],
        "supabase": {"url": s.supabase_url, "jwt_secret_configured": bool(s.supabase_jwt_secret),
                     "jwks_configured": bool(s.supabase_jwks_url)},
    }


@admin.get("/quality")
def quality(p: Principal = Depends(require_owner)) -> dict[str, Any]:
    with user_tx(p.claims) as conn:
        return _jsonable({
            "evidence": conn.execute("""select verification_status, stance::text, count(*) from public.evidence_links
                                        group by 1,2 order by 1,2""").fetchall(),
            "claims_by_category": conn.execute("select category::text, count(*) from public.claims group by 1 order by 2 desc").fetchall(),
            "claims_without_challenges": conn.execute(
                """select c.slug, c.category::text from public.claims c where not exists
                   (select 1 from public.evidence_links e where e.claim_id=c.id and e.stance='challenges')
                   and c.category in ('contested','open_question')""").fetchall(),
            "qa_results": conn.execute("""select run_id, output->'passed' as passed, output->'checks' as checks
                                          from public.harness_tasks where task_key='qa' and status='succeeded'
                                          order by finished_at desc limit 20""").fetchall(),
            "impartiality_note": "Auditoría automatizada de imparcialidad (agente #28) aún no implementada; "
                                 "se muestran indicadores de balance de evidencia.",
        })


@admin.get("/experiences")
def admin_experiences(p: Principal = Depends(require_owner)) -> list[dict[str, Any]]:
    with user_tx(p.claims) as conn:
        return _jsonable(conn.execute("""select id, run_id, modality, title, status, knowledge_packet_sha256, created_at,
                                           published_at from public.experiences order by created_at desc""").fetchall())
