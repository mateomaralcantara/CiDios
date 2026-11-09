"""Agente #8 — Descubridor bibliográfico: dimensiones 1 (textos publicados del área) y 2 (obras de expertos)."""
from __future__ import annotations

import re
from typing import Any

from ...config import get_settings
from ...connectors.openalex import OpenAlexConnector
from ...connectors.registry import CONNECTORS, sources_for
from ...db import service_tx
from ...library.embeddings import _norm
from ...library.external import ingest_candidate
from ...providers import gemini
from ..context import AgentContext

# Consultas de respaldo (en inglés: la mayor parte de la literatura académica lo está)
AREA_EN: dict[str, str] = {
    "biblia-manuscritos-critica-textual": "biblical manuscripts textual criticism", "teologia-comparada": "comparative theology",
    "historia-antigua-arqueologia": "ancient history archaeology", "filosofia-metafisica": "philosophy of religion metaphysics",
    "cosmologia-astrofisica": "cosmology origin of the universe", "fisica-fundamentos": "foundations of physics",
    "evolucion-origen-vida": "origin of life evolution", "genetica-biologia-molecular": "molecular evolution genetics",
    "neurociencia-conciencia": "neuroscience of consciousness religious experience", "antropologia-religiosa": "anthropology of religion",
    "religiones-del-mundo": "world religions history", "filosofia-moral": "moral philosophy theism",
    "milagros-afirmaciones-extraordinarias": "miracles extraordinary claims evidence", "profecias-interpretacion": "prophecy dating interpretation",
    "origen-textos-sagrados": "sacred texts transmission", "muerte-trascendencia-escatologia": "afterlife beliefs eschatology",
    "epistemologia": "religious epistemology", "ia-mente-conciencia": "artificial intelligence consciousness",
    "historia-ciencia-religion": "history of science and religion", "mal-sufrimiento-libertad-causalidad": "problem of evil free will",
}

QUERY_SCHEMA = {"type": "OBJECT", "properties": {
    "queries_en": {"type": "ARRAY", "items": {"type": "STRING"}},
    "queries_es": {"type": "ARRAY", "items": {"type": "STRING"}}}, "required": ["queries_en", "queries_es"]}


def plan_queries(question: str, topic: str | None, use_llm: bool = True) -> tuple[list[str], list[dict]]:
    """Consultas bibliográficas. Con Gemini: 3-5 en inglés y 1-2 en español. Sin Gemini: respaldo determinista."""
    usage: list[dict] = []
    if use_llm and gemini.configured():
        res = gemini.GeminiClient().generate_json(
            "Eres un bibliotecario académico. Generas consultas breves (3-8 palabras clave) para buscar literatura "
            "académica revisada por pares en OpenAlex, Crossref, Europe PMC y arXiv. Sin operadores booleanos.",
            f"Pregunta de investigación: {question}\nÁrea: {topic or 'no identificada'}\n"
            "Devuelve 3-5 consultas en inglés (queries_en) y 1-2 en español (queries_es) que cubran los aspectos "
            "principales de la pregunta, incluidas posturas en desacuerdo.",
            QUERY_SCHEMA, max_output_tokens=512)
        usage.append(res.usage())
        qs = [q.strip() for q in (res.data.get("queries_en", [])[:5] + res.data.get("queries_es", [])[:2]) if q.strip()]
        if qs:
            return qs, usage
    filler = {"dice", "dicen", "sobre", "segun", "hay", "cual", "cuales", "esta", "este", "estos", "estas", "muestrame",
              "explicame", "investiga", "what", "does", "about"}
    words = [w for w in _norm(question) if len(w) > 3 and w not in filler][:8]
    qs = [" ".join(words)] if words else [question[:120]]
    if topic in AREA_EN:
        qs.append(AREA_EN[topic])
    return qs, usage


def _relevance(question: str, title: str, abstract: str | None) -> float:
    terms = {w[:5] for w in _norm(question) if len(w) >= 4}
    if not terms:
        return 0.0
    text = {w[:5] for w in _norm(f"{title} {abstract or ''}")}
    return len(terms & text) / len(terms)


def bibliographic_discoverer(ctx: AgentContext) -> dict[str, Any]:
    mode = ctx.task_input.get("mode", "published")
    return _published(ctx) if mode == "published" else _experts(ctx)


def _published(ctx: AgentContext) -> dict[str, Any]:
    s = get_settings()
    question, topic = ctx.task_input["question"], ctx.task_input.get("topic")
    usage: list[dict] = []
    if gemini.configured():
        ctx.tool("llm.generate")
    try:
        queries, usage = plan_queries(question, topic)
    except gemini.GeminiError as e:
        ctx.log(f"Gemini no pudo planificar las consultas ({e}); se usan consultas de respaldo", level="warning")
        queries, _ = plan_queries(question, topic, use_llm=False)
    ctx.log(f"Consultas bibliográficas: {queries}", data={"queries": queries})
    sources = sources_for(topic, s.connectors_enabled)
    reports, cands = [], []
    ctx.tool("connectors.query")
    for src in sources:
        conn_ = CONNECTORS[src]()
        for q in queries:
            rep = conn_.search(q, limit=5)
            reports.append({"connector": src, "query": q, "ok": rep.ok, "n": len(rep.candidates), "error": rep.error})
            if not rep.ok:
                ctx.log(f"{src}: {rep.error}", level="warning")
                if rep.error and ("429" in rep.error or "401" in rep.error or "403" in rep.error):
                    break   # no insistir con un repositorio que rechaza las peticiones
            cands += rep.candidates
    # deduplicar por DOI/título, descartar retractadas, ordenar por pertinencia y citas
    seen, unique, retracted = set(), [], 0
    for c in cands:
        key = c.doi or re.sub(r"\W+", "", c.title.lower())[:80]
        if key in seen:
            continue
        seen.add(key)
        if c.is_retracted:
            retracted += 1
            continue
        c.extra["relevance"] = _relevance(question + " " + " ".join(queries), c.title, c.abstract)
        unique.append(c)
    unique.sort(key=lambda c: (-c.extra["relevance"], -(c.cited_by or 0)))
    picked = [c for c in unique if c.extra["relevance"] >= 0.15][: s.published_max_works]
    ctx.tool("library.ingest")
    docs = []
    with service_tx() as conn:
        for c in picked:
            d = ingest_candidate(conn, c, run_id=ctx.run_id, dimension="published")
            if d:
                d["relevance"] = round(c.extra["relevance"], 3)
                d["authors"] = [{"name": a.name, "openalex_id": a.openalex_id} for a in c.authors[:10]]
                d["cited_by"] = c.cited_by
                docs.append(d)
    if retracted:
        ctx.log(f"{retracted} obras retractadas descartadas", level="warning")
    ctx.log(f"Dimensión 1: {len(docs)} obras publicadas incorporadas (de {len(unique)} candidatas en {', '.join(sources) or 'ningún repositorio'})")
    return {"dimension": "published", "queries": queries, "sources": sources, "documents": docs,
            "chunk_ids": [cid for d in docs for cid in d["chunk_ids"]], "connector_reports": reports,
            "candidates_seen": len(unique), "retracted_excluded": retracted, "_usage": usage}


def _experts(ctx: AgentContext) -> dict[str, Any]:
    """Dimensión 2: autores con trayectoria (índice h) en el tema y sus obras revisadas por pares pertinentes."""
    s = get_settings()
    question = ctx.task_input["question"]
    d1 = ctx.deps.get("acquire_published", {})
    queries = d1.get("queries") or [question]
    if "openalex" not in s.connectors_enabled:
        ctx.log("Dimensión 2 omitida: OpenAlex desactivado (CDD_CONNECTORS_ENABLED)", level="warning")
        return {"dimension": "experts", "experts": [], "documents": [], "chunk_ids": [], "note": "OpenAlex desactivado"}
    ctx.tool("connectors.query")
    oa = OpenAlexConnector()
    # candidatos: autores de las obras de la dimensión 1 y de una búsqueda en OpenAlex
    counts: dict[str, dict[str, Any]] = {}
    for d in d1.get("documents", []):
        for a in d.get("authors", []):
            if a.get("openalex_id"):
                counts.setdefault(a["openalex_id"], {"name": a["name"], "n": 0})["n"] += 1
    rep = oa.search(queries[0], limit=10)
    if not rep.ok:
        ctx.log(f"OpenAlex: {rep.error}", level="warning")
        note = ("OpenAlex rechazó la petición: configura CDD_OPENALEX_API_KEY (gratuita)." if rep.error and "429" in rep.error
                else f"OpenAlex no disponible: {rep.error}")
        if not counts:
            return {"dimension": "experts", "experts": [], "documents": [], "chunk_ids": [], "note": note}
    for c in rep.candidates:
        for a in c.authors[:5]:
            if a.openalex_id:
                counts.setdefault(a.openalex_id, {"name": a.name, "n": 0})["n"] += 1
    ranked = sorted(counts.items(), key=lambda kv: -kv[1]["n"])[:15]
    experts = []
    for aid, _info in ranked:
        try:
            prof = oa.author(aid)
        except Exception as e:  # noqa: BLE001
            ctx.log(f"No se pudo leer el perfil {aid}: {type(e).__name__}", level="warning")
            continue
        if (prof.get("h_index") or 0) >= s.experts_min_h_index:
            experts.append(prof)
        if len(experts) >= s.experts_max_authors:
            break
    ctx.tool("library.ingest")
    docs = []
    with service_tx() as conn:
        for ex in experts:
            for c in oa.works_by_author(ex["openalex_id"], queries[0], s.experts_works_per_author):
                if c.tier != "peer_reviewed" and c.work_type not in ("book", "book-chapter", "review"):
                    continue
                if _relevance(question + " " + " ".join(queries), c.title, c.abstract) < 0.15:
                    continue
                d = ingest_candidate(conn, c, run_id=ctx.run_id, dimension="experts", tier="expert_peer_reviewed",
                                     expert={k: ex.get(k) for k in ("name", "openalex_id", "h_index", "institution")})
                if d:
                    d["expert"] = ex["name"]
                    docs.append(d)
            conn.execute(
                """insert into public.entities (slug, kind, name, description, attributes) values (%s,'person',%s,%s,%s)
                   on conflict (slug) do update set attributes = excluded.attributes""",
                ("experto-" + ex["openalex_id"].rsplit("/", 1)[-1].lower(), ex["name"],
                 f"Autor/a con índice h {ex.get('h_index')} según OpenAlex", __import__("json").dumps(ex)))
    ctx.log(f"Dimensión 2: {len(experts)} expertos (índice h ≥ {s.experts_min_h_index}) y {len(docs)} obras revisadas por pares")
    return {"dimension": "experts", "experts": experts, "documents": docs,
            "chunk_ids": [cid for d in docs for cid in d["chunk_ids"]], "min_h_index": s.experts_min_h_index}
