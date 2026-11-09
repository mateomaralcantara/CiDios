"""HARNESS SUPRA — motor de ejecución.

- Identity & Policy Engine: ``authorize``.
- Autonomous Planning: tareas de arranque (intención → plan → presupuesto) que materializan el DAG.
- Multi-Agent Orchestrator: cada DAG se compila a un ``StateGraph`` de LangGraph (ramas paralelas reales,
  uniones que esperan a todas sus dependencias).
- Recovery & Checkpoint Engine: cada tarea completada deja un checkpoint; al reanudar, las tareas ya
  completadas se reutilizan sin volver a ejecutarse ni a cobrarse.
- La cola de trabajo vive en Postgres (``queued`` + arrendamiento con ``for update skip locked``).
"""
from __future__ import annotations

import hashlib
import json
import operator
import threading
import time
import traceback
from decimal import Decimal
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from ..auth import Principal
from ..db import service_tx, user_tx
from ..experience.contracts import canonical_sha256
from ..security.injection import scan
from . import budget
from .agents.epistemic import citation_verifier, consensus_analyst
from .agents.experience import pedagogical_architect, timeline_director
from .agents.governance import budget_custodian, dag_planner, intent_interpreter
from .agents.library import universal_librarian
from .agents.quality import contract_validator
from .context import AgentContext, log_event
from .states import MAIN_CHAIN, TERMINAL, assert_transition

AGENT_FUNCTIONS = {
    "intent_interpreter": intent_interpreter, "dag_planner": dag_planner, "budget_custodian": budget_custodian,
    "universal_librarian": universal_librarian, "consensus_analyst": consensus_analyst,
    "citation_verifier": citation_verifier, "timeline_director": timeline_director,
    "pedagogical_architect": pedagogical_architect, "contract_validator": contract_validator,
}

BOOTSTRAP = [
    {"key": "intent", "agent": "intent_interpreter", "phase": "AUTHORIZED", "depends_on": [],
     "completion_criteria": "Intención estructurada"},
    {"key": "plan", "agent": "dag_planner", "phase": "AUTHORIZED", "depends_on": ["intent"],
     "completion_criteria": "DAG con criterios de terminación"},
    {"key": "budget", "agent": "budget_custodian", "phase": "PLANNED", "depends_on": ["plan"],
     "completion_criteria": "Estimación y decisión presupuestaria"},
]


class Halt(Exception):
    def __init__(self, state: str, reason: str):
        super().__init__(reason)
        self.state, self.reason = state, reason


class PolicyError(Exception):
    pass


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# ------------------------------------------------------------------ estados
def transition(run_id: str, new_state: str, reason: str = "", *, force_previous: str | None = None,
               forward_only: bool = False) -> None:
    with service_tx() as conn:
        run = conn.execute("select state::text, previous_state::text from public.harness_runs where id=%s for update",
                           (run_id,)).fetchone()
        if forward_only and not (run["state"] in MAIN_CHAIN and MAIN_CHAIN.index(new_state) > MAIN_CHAIN.index(run["state"])):
            return  # otra rama paralela ya avanzó la fase (comprobado bajo bloqueo de fila)
        assert_transition(run["state"], new_state, run["previous_state"])
        prev = force_previous or (run["state"] if run["state"] in MAIN_CHAIN else run["previous_state"])
        conn.execute(
            """update public.harness_runs set state=%s, previous_state=%s,
                 finished_at = case when %s in ('PUBLISHED','FAILED','CANCELLED','READY','PARTIAL') then now() else finished_at end
               where id=%s""", (new_state, prev, new_state, run_id))
    log_event(run_id, "state_change", f"{run['state']} → {new_state}" + (f": {reason}" if reason else ""),
              level="audit", data={"from": run["state"], "to": new_state, "reason": reason})


def _advance_to(run_id: str, phase: str) -> None:
    if phase in MAIN_CHAIN:
        transition(run_id, phase, forward_only=True)


# ------------------------------------------------------------------ creación y autorización
def _insert_tasks(conn, run_id: str, tasks: list[dict[str, Any]], extra_input: dict[str, Any] | None = None) -> None:
    for t in tasks:
        agent = conn.execute("select * from public.agent_definitions where code=%s", (t["agent"],)).fetchone()
        conn.execute(
            """insert into public.harness_tasks (run_id, task_key, agent_code, phase, depends_on, status, budget_usd,
                 allowed_tools, agent_version, input, completion_criteria)
               values (%s,%s,%s,%s,%s,'queued',%s,%s,%s,%s,%s) on conflict (run_id, task_key) do nothing""",
            (run_id, t["key"], t["agent"], t["phase"], t["depends_on"], agent["max_cost_per_run_usd"],
             agent["allowed_tools"], agent["version"], json.dumps({**(extra_input or {}), **t.get("input", {})}),
             t["completion_criteria"]))


def create_investigation(p: Principal, prompt: str, preferences: dict[str, Any] | None = None,
                         budget_usd: float | None = None, force_new: bool = False) -> dict[str, Any]:
    if not p.is_authenticated:
        raise PolicyError("Autenticación requerida")
    prompt = prompt.strip()
    if not 10 <= len(prompt) <= 4000:
        raise PolicyError("La consulta debe tener entre 10 y 4000 caracteres")
    prefs = preferences or {}
    digest = _sha(prompt.lower() + json.dumps(prefs, sort_keys=True))
    with user_tx(p.claims) as conn:
        if not force_new:
            prev = conn.execute(
                """select r.id as run_id, i.id as investigation_id from public.investigations i
                   join public.harness_runs r on r.investigation_id = i.id
                   where i.owner_id = %s and i.prompt_sha256 = %s and r.state in ('READY','PUBLISHED')
                     and r.created_at > now() - interval '7 days' order by r.created_at desc limit 1""",
                (p.user_id, digest)).fetchone()
            if prev:
                with service_tx() as s:
                    budget.record(s, run_id=str(prev["run_id"]), user_id=p.user_id, agent_code=None, kind="actual",
                                  amount=Decimal(0), cache_hit=True, note="Consulta redundante: se reutiliza la ejecución")
                return {"investigation_id": str(prev["investigation_id"]), "run_id": str(prev["run_id"]), "reused": True}
        inv = conn.execute(
            """insert into public.investigations (owner_id, prompt, prompt_sha256, preferences, status)
               values (%s,%s,%s,%s,'running') returning id""",
            (p.user_id, prompt, digest, json.dumps(prefs))).fetchone()
    budget_value = Decimal(str(budget_usd)) if budget_usd is not None else None
    with service_tx() as conn:
        if budget_value is None:
            pol = conn.execute("""select limit_usd from public.budget_policies where active and scope='investigation'
                                  and period='per_run' order by (scope_ref='*') limit 1""").fetchone()
            budget_value = Decimal(pol["limit_usd"]) if pol else Decimal("1")
        run = conn.execute(
            """insert into public.harness_runs (investigation_id, owner_id, state, budget_usd)
               values (%s,%s,'CREATED',%s) returning id""", (inv["id"], p.user_id, budget_value)).fetchone()
    run_id = str(run["id"])
    log_event(run_id, "run_created", "Investigación creada", level="audit",
              data={"investigation_id": str(inv["id"]), "budget_usd": str(budget_value)})
    authorize(run_id, p, prompt, prefs)
    return {"investigation_id": str(inv["id"]), "run_id": run_id, "reused": False}


def authorize(run_id: str, p: Principal, prompt: str, prefs: dict[str, Any]) -> None:
    """Identity & Policy Engine."""
    signals = scan(prompt)
    if signals:
        log_event(run_id, "policy", "La consulta contiene patrones de instrucciones; se procesa como texto, sin privilegios",
                  level="audit", data={"signals": signals})
    with service_tx() as conn:
        run = conn.execute("select * from public.harness_runs where id=%s", (run_id,)).fetchone()
        decision = budget.check(conn, run=run, agent={"code": "intent_interpreter", "max_cost_per_run_usd": 1e9},
                                estimate=Decimal(0))
    if not decision.allow:
        transition(run_id, "BUDGET_EXHAUSTED", decision.reason)
        return
    transition(run_id, "AUTHORIZED", f"usuario {p.user_id} rol {p.role}")
    with service_tx() as conn:
        _insert_tasks(conn, run_id, BOOTSTRAP, {"prompt": prompt, "preferences": prefs})
        conn.execute("update public.harness_runs set queued=true where id=%s", (run_id,))


# ------------------------------------------------------------------ ejecución de tareas
def _load_run(conn, run_id: str) -> dict[str, Any]:
    return conn.execute("select *, state::text as state from public.harness_runs where id=%s", (run_id,)).fetchone()


def execute_task(run_id: str, task_key: str) -> None:
    with service_tx() as conn:
        run = _load_run(conn, run_id)
        task = conn.execute("select *, status::text as status, phase::text as phase from public.harness_tasks "
                            "where run_id=%s and task_key=%s", (run_id, task_key)).fetchone()
        agent = conn.execute("select * from public.agent_definitions where code=%s", (task["agent_code"],)).fetchone()
    if run["cancel_requested"]:
        raise Halt("CANCELLED", "Cancelación solicitada")
    if run["pause_requested"]:
        raise Halt("PAUSED", "Pausa solicitada")
    if task["status"] == "succeeded":
        log_event(run_id, "checkpoint_reused", f"Tarea {task_key} recuperada de checkpoint (sin recálculo ni coste)",
                  task_key=task_key)
        return
    if agent["status"] != "operational" or not agent["enabled"]:
        with service_tx() as conn:
            conn.execute("update public.harness_tasks set status='blocked', error=%s where id=%s",
                         ("Agente deshabilitado o no operativo", task["id"]))
        raise Halt("FAILED", f"El agente {agent['code']} está deshabilitado")
    estimate = Decimal(agent["unit_cost_usd"])
    with service_tx() as conn:
        decision = budget.reserve(conn, run_id=run_id, agent=agent, estimate=estimate)
    if not decision.allow:
        raise Halt("BUDGET_EXHAUSTED", decision.reason)
    _advance_to(run_id, task["phase"])

    with service_tx() as conn:
        deps = {r["task_key"]: r["output"] for r in conn.execute(
            "select task_key, output from public.harness_tasks where run_id=%s and task_key = any(%s) and status='succeeded'",
            (run_id, task["depends_on"])).fetchall()}
        conn.execute("""update public.harness_tasks set status='running', attempts=attempts+1, started_at=now(), error=null
                        where id=%s""", (task["id"],))
    missing = set(task["depends_on"]) - set(deps)
    if missing:
        raise Halt("FAILED", f"Dependencias no satisfechas para {task_key}: {sorted(missing)}")
    log_event(run_id, "task_started", f"{task_key} ({agent['name_es']})", task_key=task_key,
              data={"agent": agent["code"], "version": agent["version"], "attempt": task["attempts"] + 1})
    ctx = AgentContext(run_id=run_id, owner_id=str(run["owner_id"]), task_key=task_key, agent_code=agent["code"],
                       allowed_tools=list(task["allowed_tools"]), task_input=task["input"], deps=deps,
                       run_plan=run["plan"])
    started = time.monotonic()
    try:
        output = AGENT_FUNCTIONS[agent["code"]](ctx)
    except Halt:
        raise
    except Exception as e:  # noqa: BLE001 — se registra y se decide reintento
        err = f"{type(e).__name__}: {e}"
        with service_tx() as conn:
            attempts = conn.execute("update public.harness_tasks set status='failed', error=%s, finished_at=now() "
                                    "where id=%s returning attempts, max_attempts", (err, task["id"])).fetchone()
            # El gasto de un intento fallido se considera consumido (las llamadas de pago se cobran igualmente).
            budget.record(conn, run_id=run_id, user_id=str(run["owner_id"]), agent_code=agent["code"], kind="actual",
                          amount=estimate, model=agent["execution_model"], note=f"{task_key}: intento fallido",
                          apply_to_run=False)
        log_event(run_id, "task_failed", f"{task_key}: {err}", level="error", task_key=task_key,
                  data={"traceback": traceback.format_exc()[-2000:]})
        if attempts["attempts"] < attempts["max_attempts"]:
            log_event(run_id, "task_retry", f"Reintentando {task_key}", level="warning", task_key=task_key)
            return execute_task(run_id, task_key)
        raise Halt("FAILED", err) from e
    elapsed = time.monotonic() - started
    cost = estimate
    digest = canonical_sha256(output)
    with service_tx() as conn:
        conn.execute("""update public.harness_tasks set status='succeeded', output=%s, cost_usd=%s, finished_at=now()
                        where id=%s""", (json.dumps(output, default=str), cost, task["id"]))
        budget.record(conn, run_id=run_id, user_id=str(run["owner_id"]), agent_code=agent["code"], kind="actual",
                      amount=cost, model=agent["execution_model"], note=f"{task_key} en {elapsed:.2f}s",
                      apply_to_run=False)  # ya reservado atómicamente antes de ejecutar
        conn.execute("""insert into public.harness_checkpoints (run_id, task_key, state, output_sha256, snapshot)
                        values (%s,%s,%s,%s,%s) on conflict (run_id, task_key) do update
                        set output_sha256=excluded.output_sha256, snapshot=excluded.snapshot, created_at=now()""",
                     (run_id, task_key, task["phase"], digest, json.dumps({"output_keys": sorted(output)})))
    log_event(run_id, "task_succeeded", f"{task_key} completada en {elapsed:.2f}s", task_key=task_key,
              data={"cost_usd": str(cost), "output_sha256": digest})


# ------------------------------------------------------------------ LangGraph
class _GraphState(TypedDict):
    done: Annotated[list[str], operator.add]


def build_graph(run_id: str, tasks: list[dict[str, Any]]):
    g = StateGraph(_GraphState)
    keys = {t["task_key"] for t in tasks}

    def make_node(key: str):
        def node(_state: _GraphState) -> dict[str, list[str]]:
            execute_task(run_id, key)
            return {"done": [key]}
        return node

    for t in tasks:
        g.add_node(t["task_key"], make_node(t["task_key"]))
    has_successor: set[str] = set()
    for t in tasks:
        deps = [d for d in t["depends_on"] if d in keys]
        if not deps:
            g.add_edge(START, t["task_key"])
        elif len(deps) == 1:
            g.add_edge(deps[0], t["task_key"])
        else:
            g.add_edge(deps, t["task_key"])  # unión: espera a todas las dependencias
        has_successor.update(deps)
    for t in tasks:
        if t["task_key"] not in has_successor:
            g.add_edge(t["task_key"], END)
    return g.compile()


def _run_graph(run_id: str, keys: list[str] | None = None) -> None:
    with service_tx() as conn:
        tasks = conn.execute("select task_key, depends_on from public.harness_tasks where run_id=%s order by created_at",
                             (run_id,)).fetchall()
    if keys is not None:
        tasks = [t for t in tasks if t["task_key"] in keys]
    build_graph(run_id, tasks).invoke({"done": []}, {"max_concurrency": 4, "recursion_limit": 100})


def _research_keys(run_id: str) -> list[str]:
    boot = {t["key"] for t in BOOTSTRAP}
    with service_tx() as conn:
        return [r["task_key"] for r in conn.execute("select task_key from public.harness_tasks where run_id=%s",
                                                    (run_id,)).fetchall() if r["task_key"] not in boot]


def _materialize_plan(run_id: str) -> bool:
    """Tras el arranque: inserta el DAG planificado. Devuelve False si la ejecución debe detenerse."""
    with service_tx() as conn:
        outs = {r["task_key"]: r["output"] for r in conn.execute(
            "select task_key, output from public.harness_tasks where run_id=%s and task_key in ('intent','plan','budget')",
            (run_id,)).fetchall()}
        run = _load_run(conn, run_id)
        plan = outs["plan"]["plan"]
        conn.execute("update public.harness_runs set plan=%s where id=%s", (json.dumps(plan), run_id))
        conn.execute("update public.investigations set intent=%s where id=%s",
                     (json.dumps(outs["intent"]["intent"]), run["investigation_id"]))
        _insert_tasks(conn, run_id, plan["tasks"])
    b = outs["budget"]
    if not b["within_budget"]:
        transition(run_id, "BUDGET_EXHAUSTED", f"Estimación {b['estimate_usd']} supera el presupuesto {b['budget_usd']}")
        return False
    if b["requires_approval"] and run["approved_at"] is None:
        with service_tx() as conn:
            conn.execute("update public.harness_runs set requires_approval=true where id=%s", (run_id,))
        transition(run_id, "AWAITING_APPROVAL",
                   f"Gasto estimado {b['estimate_usd']} USD supera el umbral de aprobación automática {b['auto_approve_below_usd']}")
        return False
    return True


def _finalize(run_id: str) -> None:
    with service_tx() as conn:
        outs = {r["task_key"]: r["output"] for r in conn.execute(
            "select task_key, output from public.harness_tasks where run_id=%s and status='succeeded'", (run_id,)).fetchall()}
        run = _load_run(conn, run_id)
    qa = outs.get("qa", {})
    if not qa.get("passed"):
        transition(run_id, "FAILED", "El control de calidad no superó todas las comprobaciones")
        with service_tx() as conn:
            conn.execute("update public.investigations set status='failed' where id=%s", (run["investigation_id"],))
        return
    packet = outs["package"]["knowledge_packet"]
    spec = outs["render"]["experience_spec"]
    with service_tx() as conn:
        exp = conn.execute(
            """insert into public.experiences (run_id, owner_id, modality, title, knowledge_packet, knowledge_packet_sha256,
                 experience_spec, status) values (%s,%s,%s,%s,%s,%s,%s,'ready') returning id""",
            (run_id, run["owner_id"], spec["modality"], spec["title"], json.dumps(packet), packet["sha256"],
             json.dumps(spec))).fetchone()
        conn.execute("update public.harness_runs set result=%s, queued=false where id=%s",
                     (json.dumps({"experience_id": str(exp["id"]), "claims": len(packet["claims"]),
                                  "excluded": len(packet["excluded_claims"])}), run_id))
        conn.execute("update public.investigations set status='ready' where id=%s", (run["investigation_id"],))
    transition(run_id, "READY", f"Experiencia {exp['id']} lista para revisión")


def process_run(run_id: str) -> str:
    """Ejecuta (o reanuda) una investigación hasta un estado estable. Devuelve el estado final."""
    with service_tx() as conn:
        run = _load_run(conn, run_id)
        conn.execute("update public.harness_runs set queued=false where id=%s", (run_id,))
    if run["state"] in TERMINAL or run["state"] in ("READY", "PARTIAL"):
        return run["state"]
    try:
        _run_graph(run_id, ["intent", "plan", "budget"])
        with service_tx() as conn:
            planned = conn.execute("select count(*) as n from public.harness_tasks where run_id=%s", (run_id,)).fetchone()["n"] > 3
        if not planned:
            if not _materialize_plan(run_id):
                return _state(run_id)
        _run_graph(run_id, _research_keys(run_id))
        _finalize(run_id)
    except Halt as h:
        cur = _state(run_id)
        if cur not in TERMINAL and cur != h.state:
            transition(run_id, h.state, h.reason)
        if h.state == "FAILED":
            with service_tx() as conn:
                conn.execute("update public.harness_runs set error=%s where id=%s", (h.reason, run_id))
                conn.execute("""update public.investigations set status='failed' where id =
                                (select investigation_id from public.harness_runs where id=%s)""", (run_id,))
    except Exception as e:  # noqa: BLE001
        with service_tx() as conn:
            conn.execute("update public.harness_runs set error=%s where id=%s", (f"{type(e).__name__}: {e}", run_id))
        if _state(run_id) not in TERMINAL:
            transition(run_id, "FAILED", f"Error inesperado: {type(e).__name__}")
    return _state(run_id)


def _state(run_id: str) -> str:
    with service_tx() as conn:
        return conn.execute("select state::text from public.harness_runs where id=%s", (run_id,)).fetchone()["state"]


# ------------------------------------------------------------------ control del propietario / usuario
def request_pause(run_id: str) -> None:
    with service_tx() as conn:
        conn.execute("update public.harness_runs set pause_requested=true where id=%s", (run_id,))
    log_event(run_id, "control", "Pausa solicitada", level="audit")


def request_cancel(run_id: str) -> str:
    with service_tx() as conn:
        conn.execute("update public.harness_runs set cancel_requested=true, queued=false where id=%s", (run_id,))
    log_event(run_id, "control", "Cancelación solicitada", level="audit")
    st = _state(run_id)
    if st not in TERMINAL and st not in ("READY", "PARTIAL"):
        # Si no hay un worker activo (pausada, en espera, etc.), se cancela de inmediato.
        if st in ("PAUSED", "AWAITING_APPROVAL", "BUDGET_EXHAUSTED", "LICENSE_BLOCKED", "CREATED", "AUTHORIZED"):
            transition(run_id, "CANCELLED", "Cancelada por solicitud")
    return _state(run_id)


def resume(run_id: str) -> str:
    with service_tx() as conn:
        run = _load_run(conn, run_id)
    if run["state"] not in ("PAUSED", "BUDGET_EXHAUSTED", "AWAITING_APPROVAL"):
        raise PolicyError(f"No se puede reanudar desde {run['state']}")
    if run["state"] == "AWAITING_APPROVAL" and run["approved_at"] is None:
        raise PolicyError("La ejecución requiere aprobación del propietario")
    target = run["previous_state"] or "AUTHORIZED"
    transition(run_id, target, "Reanudación")
    with service_tx() as conn:
        conn.execute("update public.harness_runs set pause_requested=false, queued=true where id=%s", (run_id,))
    return target


def approve(run_id: str, owner: Principal) -> str:
    with service_tx() as conn:
        conn.execute("update public.harness_runs set approved_by=%s, approved_at=now() where id=%s", (owner.user_id, run_id))
    log_event(run_id, "approval", f"Gasto aprobado por el propietario {owner.user_id}", level="audit")
    return resume(run_id)


def set_budget(run_id: str, amount: Decimal, owner: Principal) -> None:
    with service_tx() as conn:
        conn.execute("update public.harness_runs set budget_usd=%s where id=%s", (amount, run_id))
    log_event(run_id, "budget_changed", f"Presupuesto fijado en {amount} USD por {owner.user_id}", level="audit")


def publish(run_id: str, owner: Principal) -> str:
    with service_tx() as conn:
        exp = conn.execute("select id from public.experiences where run_id=%s", (run_id,)).fetchone()
        if exp is None:
            raise PolicyError("No hay experiencia para publicar")
    transition(run_id, "PUBLISHED", f"Publicado por {owner.user_id}")
    with service_tx() as conn:
        conn.execute("update public.experiences set status='published', published_by=%s, published_at=now() where id=%s",
                     (owner.user_id, exp["id"]))
        conn.execute("""update public.investigations set status='published' where id =
                        (select investigation_id from public.harness_runs where id=%s)""", (run_id,))
    return str(exp["id"])


# ------------------------------------------------------------------ worker
def claim_next_run() -> str | None:
    with service_tx() as conn:
        row = conn.execute(
            """update public.harness_runs set worker_lease_until = now() + interval '10 minutes'
               where id = (select id from public.harness_runs where queued
                           and (worker_lease_until is null or worker_lease_until < now())
                           order by created_at for update skip locked limit 1)
               returning id""").fetchone()
    return str(row["id"]) if row else None


class Worker(threading.Thread):
    def __init__(self, poll_s: float = 0.5):
        super().__init__(daemon=True, name="harness-worker")
        self.poll_s, self._stop = poll_s, threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        while not self._stop.is_set():
            run_id = None
            try:
                run_id = claim_next_run()
                if run_id:
                    process_run(run_id)
            except Exception:  # noqa: BLE001
                traceback.print_exc()
            finally:
                if run_id:
                    with service_tx() as conn:
                        conn.execute("update public.harness_runs set worker_lease_until=null where id=%s", (run_id,))
            if not run_id:
                self._stop.wait(self.poll_s)
