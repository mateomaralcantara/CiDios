"""Familia I — Gobernanza: Intérprete de intención (#1), Planificador DAG (#2), Custodio de presupuesto (#5)."""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal
from typing import Any

from ...db import service_tx
from .. import budget
from ..context import AgentContext

SUPPORTED_MODALITIES = {"article", "comparison_matrix", "timeline", "gamified_timeline"}

_TOPIC_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("biblia-manuscritos-critica-textual", ("biblia", "biblico", "manuscrit", "critica textual", "textos biblicos",
                                            "codice", "papiro", "septuaginta", "qumran", "mar muerto", "masoret", "vulgata")),
    ("cosmologia-astrofisica", ("cosmolog", "big bang", "universo", "galaxia", "astrofis")),
    ("evolucion-origen-vida", ("evolucion", "darwin", "origen de la vida", "abiogenesis")),
    ("neurociencia-conciencia", ("neurocien", "conciencia", "cerebro")),
    ("filosofia-metafisica", ("metafisic", "argumento cosmologico", "ontologic")),
    ("mal-sufrimiento-libertad-causalidad", ("problema del mal", "sufrimiento", "libre albedrio")),
    ("religiones-del-mundo", ("religiones", "islam", "budis", "hindu")),
    ("ia-mente-conciencia", ("inteligencia artificial", " ia ", "mente artificial")),
]

_MODALITY_KEYWORDS = [
    ("gamified_timeline", ("gamificad", "juego", "misiones", "mision")),
    ("timeline", ("linea de tiempo", "linea temporal", "cronologia", "timeline")),
    ("comparison_matrix", ("compara", "matriz", "perspectivas")),
    ("research_report", ("informe academico", "informe de investigacion")),
    ("atlas", ("atlas",)), ("podcast", ("podcast",)), ("mini_documentary", ("documental",)),
    ("knowledge_graph", ("grafo",)), ("debate", ("debate",)), ("explorable_3d", (" 3d",)),
    ("article", ("articulo", "explica", "que es")),
]

_WANTS = {
    "maps": ("mapa",), "narration": ("narracion", "narrador", "narrada"), "sources": ("fuentes", "citas", "referencias"),
    "quizzes": ("preguntas", "quiz", "test"), "missions": ("mision",), "illustrations": ("ilustr", "imagen"),
    "uncertainties": ("incertidumbre", "dudas"), "positions": ("posiciones", "posturas", "perspectivas"),
    "dates": ("datacion", "fechas", "cronolog"), "evidence": ("evidencia", "pruebas"),
}

# Plan de recuperación por épocas para el área bíblica (subconsultas de la investigación).
_BIBLE_ERAS: list[tuple[str, list[str]]] = [
    ("antiguedad", ["amuletos de plata bendición sacerdotal datación", "papiro Nash Decálogo Shemá",
                    "traducción griega del Pentateuco Septuaginta Alejandría",
                    "manuscritos de Qumrán datación radiocarbono", "gran rollo de Isaías", "pluriformidad textual Segundo Templo",
                    "comunidad de Qumrán esenios debate"]),
    ("papiros_codices", ["papiro P52 Juan datación paleográfica", "papiro P46 cartas paulinas", "papiro P75 Lucas Juan Vaticano",
                         "Códice Sinaítico Nuevo Testamento completo", "Códice Vaticano siglo IV", "Códice Alejandrino"]),
    ("medieval", ["Vulgata Jerónimo traducción del hebreo", "masoretas vocales acentos masora Tiberíades",
                  "Códice de Alepo", "Códice de Leningrado colofón"]),
    ("moderna", ["Biblia de Gutenberg imprenta", "Políglota Complutense Alcalá", "Erasmo Nuevo Testamento griego 1516",
                 "Segunda Biblia Rabínica Bomberg", "Biblia del Oso Casiodoro de Reina", "Textus Receptus Elzevir",
                 "Westcott Hort edición crítica", "Biblia Hebraica Stuttgartensia Quinta", "Nestle-Aland Editio Critica Maior",
                 "descubrimiento manuscritos mar Muerto cuevas", "autógrafo manuscrito original", "reconstruir texto original"]),
]


def _fold(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.lower())
    return " " + "".join(c for c in t if not unicodedata.combining(c)) + " "


def interpret(prompt: str, preferences: dict[str, Any] | None = None) -> dict[str, Any]:
    prefs = preferences or {}
    f = _fold(prompt)
    topic = next((slug for slug, kws in _TOPIC_KEYWORDS if any(k in f for k in kws)), None)
    requested = prefs.get("modality") or next((m for m, kws in _MODALITY_KEYWORDS if any(k in f for k in kws)), "article")
    modality, notes = requested, []
    if requested not in SUPPORTED_MODALITIES:
        modality = "article"
        notes.append(f"La modalidad «{requested}» aún no está implementada en esta versión; se entrega un artículo enciclopédico.")
    wants = sorted(k for k, kws in _WANTS.items() if any(kw in f for kw in kws))
    english = len(re.findall(r"\b(the|and|of|show|history|timeline)\b", prompt.lower()))
    spanish = len(re.findall(r"\b(el|la|de|los|las|y|muéstrame|historia)\b", prompt.lower()))
    ambiguities = []
    if topic is None:
        ambiguities.append("No se identificó un área de la enciclopedia con contenido; la investigación usará la biblioteca completa.")
    return {
        "topic": topic, "modality": modality, "requested_modality": requested, "wants": wants,
        "language": prefs.get("language") or ("en" if english > spanish else "es"),
        "depth": prefs.get("depth") or ("deep" if any(k in f for k in ("investiga", "academic", "evidencias")) else "standard"),
        "audience": prefs.get("level") or "general",
        "time_scope": "full" if (" desde " in f and " hasta " in f) else "unspecified",
        "academic_mode": bool(prefs.get("academic_mode", False)),
        "ambiguities": ambiguities, "notes": notes,
    }


def intent_interpreter(ctx: AgentContext) -> dict[str, Any]:
    ctx.tool("intent.classify")
    intent = interpret(ctx.task_input["prompt"], ctx.task_input.get("preferences"))
    for n in intent["notes"] + intent["ambiguities"]:
        ctx.log(n, level="warning")
    return {"intent": intent}


def build_plan(intent: dict[str, Any], prompt: str, operational: set[str]) -> dict[str, Any]:
    if intent["topic"] == "biblia-manuscritos-critica-textual":
        groups = [(name, qs) for name, qs in _BIBLE_ERAS]
    else:
        groups = [("general", [prompt])]
    tasks: list[dict[str, Any]] = []
    acq_keys = []
    for name, qs in groups:
        key = f"acquire_{name}"
        acq_keys.append(key)
        tasks.append({"key": key, "agent": "universal_librarian", "phase": "ACQUIRING", "depends_on": [],
                      "input": {"queries": qs + ([prompt] if name == groups[0][0] else []), "topic": intent["topic"]},
                      "completion_criteria": "Al menos un fragmento recuperado o ausencia documentada"})
    tasks += [
        {"key": "analyze", "agent": "consensus_analyst", "phase": "ANALYZING", "depends_on": acq_keys,
         "input": {"mode": "analyze", "topic": intent["topic"]},
         "completion_criteria": "Afirmaciones candidatas agrupadas y cobertura temporal evaluada"},
        {"key": "cross_examine", "agent": "consensus_analyst", "phase": "CROSS_EXAMINING", "depends_on": ["analyze"],
         "input": {"mode": "cross_examine"},
         "completion_criteria": "Cada afirmación con balance de evidencia, perspectivas e incertidumbres"},
        {"key": "verify", "agent": "citation_verifier", "phase": "VERIFYING", "depends_on": ["cross_examine"],
         "input": {"mode": "verify"}, "completion_criteria": "Toda cita comprobada literalmente contra su fuente"},
        {"key": "package", "agent": "citation_verifier", "phase": "PACKAGING", "depends_on": ["verify", "cross_examine", "analyze"],
         "input": {"mode": "package"}, "completion_criteria": "KnowledgePacket con hash de integridad"},
    ]
    renderer = "timeline_director" if intent["modality"] in ("timeline", "gamified_timeline") else "pedagogical_architect"
    tasks += [
        {"key": "render", "agent": renderer, "phase": "RENDERING", "depends_on": ["package"],
         "input": {"modality": intent["modality"], "gamified": intent["modality"] == "gamified_timeline"},
         "completion_criteria": "ExperienceSpec que solo referencia afirmaciones del paquete"},
        {"key": "qa", "agent": "contract_validator", "phase": "QA", "depends_on": ["render", "package"], "input": {},
         "completion_criteria": "Todas las comprobaciones de contrato superadas"},
    ]
    missing = sorted({t["agent"] for t in tasks} - operational)
    if missing:
        raise RuntimeError(f"El plan requiere agentes no operativos o deshabilitados: {missing}")
    return {"tasks": tasks, "renderer": renderer, "parallel_groups": [acq_keys]}


def dag_planner(ctx: AgentContext) -> dict[str, Any]:
    ctx.tool("plan.build")
    intent = ctx.deps["intent"]["intent"]
    with service_tx() as conn:
        operational = {r["code"] for r in conn.execute(
            "select code from public.agent_definitions where status='operational' and enabled").fetchall()}
    plan = build_plan(intent, ctx.task_input["prompt"], operational)
    ctx.log(f"Plan con {len(plan['tasks'])} tareas; adquisición paralela en {len(plan['parallel_groups'][0])} ramas")
    return {"plan": plan}


def budget_custodian(ctx: AgentContext) -> dict[str, Any]:
    ctx.tool("budget.read")
    plan = ctx.deps["plan"]["plan"]
    with service_tx() as conn:
        costs = {r["code"]: Decimal(r["unit_cost_usd"]) for r in conn.execute(
            "select code, unit_cost_usd from public.agent_definitions").fetchall()}
        estimate = sum((costs.get(t["agent"], Decimal(0)) for t in plan["tasks"]), Decimal(0))
        run = conn.execute("select * from public.harness_runs where id=%s", (ctx.run_id,)).fetchone()
        threshold = budget.approval_threshold(conn)
        ctx.tool("budget.reserve")
        budget.record(conn, run_id=ctx.run_id, user_id=ctx.owner_id, agent_code=None, kind="estimate", amount=estimate,
                      note="Estimación del plan completo")
        conn.execute("update public.harness_runs set estimated_usd=%s where id=%s", (estimate, ctx.run_id))
    within = Decimal(run["spent_usd"]) + estimate <= Decimal(run["budget_usd"])
    requires_approval = estimate > threshold and run["approved_at"] is None
    return {"estimate_usd": str(estimate), "budget_usd": str(run["budget_usd"]), "within_budget": within,
            "requires_approval": requires_approval, "auto_approve_below_usd": str(threshold)}
