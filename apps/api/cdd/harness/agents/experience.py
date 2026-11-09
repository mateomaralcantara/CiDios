"""Familia V — Director de líneas de tiempo (#31) y Arquitecto pedagógico (#29): Experience Compiler.

Reglas: el ExperienceSpec solo referencia afirmaciones del KnowledgePacket; los textos narrados son las
afirmaciones literales; las ilustraciones son esquemas originales marcados como tales; las decisiones del
jugador nunca alteran la historia (las misiones solo desbloquean etapas de contenido idéntico).
"""
from __future__ import annotations

import hashlib
from typing import Any

from ...experience.contracts import (
    ArticleSection,
    ExperienceSpec,
    Illustration,
    KnowledgePacket,
    MapPoint,
    MapSpec,
    Mission,
    Provenance,
    Question,
    Stage,
    TimelineEvent,
)
from ..context import AgentContext

STAGES = [
    ("antiguedad", "Antigüedad: los primeros testimonios", -10_000, 0, "hasta el s. I a. e. c.",
     "Antes de los códices: amuletos, papiros y rollos. Aquí verás qué se conserva y qué se discute de su datación."),
    ("papiros-codices", "Papiros y grandes códices", 1, 499, "s. I – V e. c.",
     "Los textos cristianos se copian en códices de papiro y luego de pergamino. La datación paleográfica tiene márgenes amplios."),
    ("edad-media", "Masoretas, Vulgata y Edad Media", 500, 1399, "s. VI – XIV",
     "Escribas judíos fijan vocales y acentos; la Biblia latina se difunde. Aparecen los códices hebreos completos más antiguos."),
    ("imprenta", "La imprenta y las primeras ediciones", 1400, 1799, "s. XV – XVIII",
     "La imprenta multiplica el texto. Las primeras ediciones se basan en pocos manuscritos tardíos."),
    ("ediciones-criticas", "Descubrimientos y ediciones críticas", 1800, 3000, "s. XIX – hoy",
     "Grandes hallazgos y ediciones críticas que comparan miles de testimonios. Los autógrafos no se conservan."),
]

ILLUSTRATION_ALT = {
    "scroll": "Esquema de un rollo", "codex": "Esquema de un códice encuadernado", "papyrus": "Esquema de un fragmento de papiro",
    "amulet": "Esquema de un pequeño rollo de plata", "printed_book": "Esquema de un libro impreso",
    "critical_edition": "Esquema de una edición crítica con aparato",
}


def _det_shuffle(options: list[str], seed: str) -> tuple[list[str], int]:
    correct = options[0]
    ordered = sorted(options, key=lambda o: hashlib.sha256((seed + o).encode()).hexdigest())
    return ordered, ordered.index(correct)


def _illustration(kind: str | None, title: str) -> Illustration:
    k = kind or "codex"
    return Illustration(kind=k, alt=f"{ILLUSTRATION_ALT.get(k, 'Esquema')} — {title}", provenance=Provenance(
        creator="Ciencia de Dios (ilustración vectorial generada por código)", kind="schematic_illustration",
        license="CC-BY-4.0", is_reconstruction=True,
        notice="Ilustración esquemática original: representa el tipo de soporte, no reproduce el manuscrito real."))


def _questions(stage_events: list, all_events: list, packet: KnowledgePacket, stage_id: str) -> list[Question]:
    by_id = {c.id: c for c in packet.claims}
    qs: list[Question] = []
    labels = sorted({by_id[e.claim_id].date.label for e in all_events if by_id[e.claim_id].date})
    places = sorted({by_id[e.claim_id].place.name for e in all_events if by_id[e.claim_id].place})
    cats = sorted({c.category_label for c in packet.claims})
    for i, ev in enumerate(stage_events[:3]):
        c = by_id[ev.claim_id]
        seed = f"{stage_id}:{c.id}"
        if i % 3 == 0 and c.date:
            distract = [lb for lb in labels if lb != c.date.label][:]
            distract = sorted(distract, key=lambda x: hashlib.sha256((seed + x).encode()).hexdigest())[:3]
            opts, idx = _det_shuffle([c.date.label] + distract, seed)
            unc = f" Precisión de la fecha: {c.date.precision_label}." + (
                f" {c.insufficient_evidence_note}" if c.insufficient_evidence_note else "")
            qs.append(Question(id=f"q-{stage_id}-{i}", claim_id=c.id, kind="dating",
                               prompt=f"¿Qué datación corresponde a «{ev.title}»?", options=opts, correct_index=idx,
                               explanation=c.statement + unc))
        elif i % 3 == 1 and c.place:
            distract = sorted([p for p in places if p != c.place.name],
                              key=lambda x: hashlib.sha256((seed + x).encode()).hexdigest())[:3]
            opts, idx = _det_shuffle([c.place.name] + distract, seed)
            qs.append(Question(id=f"q-{stage_id}-{i}", claim_id=c.id, kind="place",
                               prompt=f"¿Con qué lugar se relaciona «{ev.title}» en esta línea de tiempo?", options=opts,
                               correct_index=idx, explanation=c.statement))
        else:
            distract = sorted([x for x in cats if x != c.category_label],
                              key=lambda x: hashlib.sha256((seed + x).encode()).hexdigest())[:3]
            opts, idx = _det_shuffle([c.category_label] + distract, seed)
            qs.append(Question(id=f"q-{stage_id}-{i}", claim_id=c.id, kind="epistemic_category",
                               prompt=f"¿Cómo clasifica Ciencia de Dios esta afirmación? «{c.statement}»", options=opts,
                               correct_index=idx,
                               explanation=f"Se clasifica como «{c.category_label}». " + (c.consensus_note or c.insufficient_evidence_note or
                                           "La clasificación depende del tipo de evidencia disponible, no de una preferencia.")))
    return qs


def compile_timeline(packet: KnowledgePacket, gamified: bool, title: str) -> ExperienceSpec:
    events: list[TimelineEvent] = []
    for c in packet.claims:
        if not (c.is_event and c.date):
            continue
        sid = next(s[0] for s in STAGES if s[2] <= c.date.start <= s[3])
        events.append(TimelineEvent(
            claim_id=c.id, title=c.subject or c.slug, sort_key=float(c.date.start), date_label=c.date.label,
            precision=c.date.precision, stage_id=sid, narration=c.statement,
            illustration=_illustration(c.illustration_kind, c.subject or c.slug),
            place_name=c.place.name if c.place else None))
    events.sort(key=lambda e: (e.sort_key, e.title))
    stages: list[Stage] = []
    for sid, stitle, _lo, _hi, rlabel, intro in STAGES:
        sev = [e for e in events if e.stage_id == sid]
        if not sev:
            continue
        mission = None
        if gamified:
            qs = _questions(sev, events, packet, sid)
            mission = Mission(id=f"m-{sid}", title=f"Misión: {stitle}",
                              objective="Responde las preguntas usando las fuentes de cada evento. Acertar la mitad desbloquea la siguiente etapa.",
                              questions=qs) if qs else None
        stages.append(Stage(id=sid, index=len(stages), title=stitle, range_label=rlabel, intro=intro,
                            event_claim_ids=[e.claim_id for e in sev], mission=mission))
    points: dict[str, MapPoint] = {}
    for c in packet.claims:
        if c.place and c.place.lat is not None and c.place.lon is not None:
            p = points.setdefault(c.place.name, MapPoint(name=c.place.name, lat=c.place.lat, lon=c.place.lon, claim_ids=[]))
            p.claim_ids.append(c.id)
    lats = [p.lat for p in points.values()] or [0]
    lons = [p.lon for p in points.values()] or [0]
    notices = ["Las fechas se muestran con su grado de precisión; los intervalos y dataciones discutidas se señalan como tales.",
               "Las misiones solo desbloquean contenido: ninguna respuesta modifica los hechos presentados."]
    open_q = [c for c in packet.claims if not c.is_event]
    if open_q:
        notices.append(f"{len(open_q)} afirmaciones sin fecha (consensos generales y cuestiones abiertas) se muestran en el panel de contexto.")
    return ExperienceSpec(
        modality="gamified_timeline" if gamified else "timeline", title=title, packet_sha256=packet.sha256,
        gamified=gamified, narration={"engine": "browser-speech-synthesis", "paid": False, "optional": True,
                                      "source": "afirmaciones literales del KnowledgePacket"},
        stages=stages, events=events,
        map=MapSpec(notice="Mapa esquemático (proyección equirectangular, sin cartografía base). Las ubicaciones son "
                           "lugares de producción, hallazgo o conservación según cada afirmación.",
                    bounds={"min_lat": min(lats) - 3, "max_lat": max(lats) + 3, "min_lon": min(lons) - 3, "max_lon": max(lons) + 3},
                    points=list(points.values())),
        notices=notices)


def timeline_director(ctx: AgentContext) -> dict[str, Any]:
    ctx.tool("experience.compile")
    packet = KnowledgePacket.model_validate(ctx.deps["package"]["knowledge_packet"])
    title = "La transmisión de los textos bíblicos" if packet.topic == "biblia-manuscritos-critica-textual" else packet.question[:80]
    spec = compile_timeline(packet, ctx.task_input.get("gamified", False), title)
    ctx.log(f"Línea de tiempo: {len(spec.events)} eventos en {len(spec.stages)} etapas; "
            f"{sum(len(s.mission.questions) for s in spec.stages if s.mission)} preguntas")
    return {"experience_spec": spec.model_dump()}


def pedagogical_architect(ctx: AgentContext) -> dict[str, Any]:
    ctx.tool("experience.compile")
    packet = KnowledgePacket.model_validate(ctx.deps["package"]["knowledge_packet"])
    known = [c.id for c in packet.claims if c.category in ("empirical_fact", "historical_document", "scholarly_consensus")]
    debated = [c.id for c in packet.claims if c.category in ("contested", "scientific_hypothesis", "uncorroborated")]
    interp = [c.id for c in packet.claims if c.category in ("philosophical_argument", "theological_interpretation", "religious_belief")]
    open_ = [c.id for c in packet.claims if c.category == "open_question"]
    sections = [s for s in [
        ArticleSection(heading="Lo que documentan las fuentes", claim_ids=known,
                       intro="Hechos, documentos y consensos académicos, cada uno con sus citas."),
        ArticleSection(heading="Lo que se debate", claim_ids=debated, intro="Afirmaciones con evidencia en sentidos distintos."),
        ArticleSection(heading="Interpretaciones y argumentos", claim_ids=interp, intro=""),
        ArticleSection(heading="Preguntas abiertas", claim_ids=open_, intro="Lo que hoy no puede responderse con seguridad."),
    ] if s.claim_ids]
    modality = ctx.task_input.get("modality", "article")
    spec = ExperienceSpec(modality="comparison_matrix" if modality == "comparison_matrix" else "article",
                          title=packet.question[:100], packet_sha256=packet.sha256, sections=sections,
                          notices=["Artículo compilado a partir del KnowledgePacket verificado."])
    return {"experience_spec": spec.model_dump()}
