"""Carga idempotente del catálogo inicial: licencias, referencias, áreas, corpus verificado,
agentes, políticas de presupuesto y (opcionalmente) usuarios de desarrollo.

Uso: python -m cdd.seed [--dev-users]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from typing import Any

from psycopg import Connection

from .db import service_tx
from .harness.registry import AGENTS
from .library.ingest import DocumentInput, DuplicateDocument, ingest_document
from .paths import corpus_dir
from .topics import AREAS

DEV_USERS = {
    "owner": ("00000000-0000-4000-8000-000000000001", "propietario@cienciaydios.local", "owner"),
    "user": ("00000000-0000-4000-8000-000000000002", "usuario@cienciaydios.local", "user"),
    "user2": ("00000000-0000-4000-8000-000000000003", "usuaria2@cienciaydios.local", "user"),
}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def seed_agents(conn: Connection) -> None:
    for a in AGENTS:
        conn.execute(
            """insert into public.agent_definitions (code, number, family, name_es, version, status, enabled, execution_model,
                 allowed_tools, input_contract, output_contract, rules, unit_cost_usd, max_cost_per_run_usd, fallback)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               on conflict (code) do update set family=excluded.family, name_es=excluded.name_es, version=excluded.version,
                 status=excluded.status, execution_model=excluded.execution_model, allowed_tools=excluded.allowed_tools,
                 input_contract=excluded.input_contract, output_contract=excluded.output_contract, rules=excluded.rules,
                 fallback=excluded.fallback, updated_at=now(),
                 -- un agente que pasa a estar implementado queda habilitado con su coste por defecto
                 enabled = case when agent_definitions.status <> 'operational' and excluded.status = 'operational'
                                then true else agent_definitions.enabled end,
                 unit_cost_usd = case when agent_definitions.status <> 'operational' and excluded.status = 'operational'
                                then excluded.unit_cost_usd else agent_definitions.unit_cost_usd end""",
            (a.code, a.number, a.family, a.name_es, a.version, a.status, a.status == "operational", a.execution_model,
             list(a.allowed_tools), a.input_contract or "—", a.output_contract or "—", list(a.rules), a.unit_cost_usd,
             a.max_cost_per_run_usd, a.fallback),
        )


def seed_budgets(conn: Connection) -> None:
    for scope, ref, period, limit in [
        ("global", "*", "daily", 25), ("global", "*", "monthly", 300),
        ("user", "*", "daily", 5), ("investigation", "*", "per_run", 1),
    ]:
        conn.execute(
            """insert into public.budget_policies (scope, scope_ref, period, limit_usd) values (%s,%s,%s,%s)
               on conflict (scope, scope_ref, period) do nothing""", (scope, ref, period, limit))


def seed_dev_users(conn: Connection) -> None:
    for _, (uid, email, role) in DEV_USERS.items():
        conn.execute("insert into auth.users (id, email) values (%s,%s) on conflict (id) do nothing", (uid, email))
        conn.execute("insert into public.profiles (id, display_name) values (%s,%s) on conflict (id) do nothing",
                     (uid, email.split("@")[0]))
        conn.execute("insert into public.user_roles (user_id, role) values (%s,%s) on conflict (user_id) do update set role=excluded.role",
                     (uid, role))


def seed_topics(conn: Connection) -> dict[str, str]:
    ids = {}
    for i, (slug, title, summary) in enumerate(AREAS):
        row = conn.execute(
            """insert into public.topics (slug, title, summary, sort_order) values (%s,%s,%s,%s)
               on conflict (slug) do update set title=excluded.title, summary=excluded.summary returning id""",
            (slug, title, summary, i)).fetchone()
        ids[slug] = str(row["id"])
    return ids


def _find_chunk(conn: Connection, doc_id: str, fragment: str) -> dict[str, Any]:
    row = conn.execute(
        """select id, locator from public.document_chunks
           where document_id = %s and position(regexp_replace(%s, '\\s+', ' ', 'g') in regexp_replace(content, '\\s+', ' ', 'g')) > 0
           order by ordinal limit 1""", (doc_id, fragment)).fetchone()
    if row is None:
        raise ValueError(f"Fragmento no encontrado en el documento {doc_id}: {fragment[:80]!r}")
    return row


def seed_corpus(conn: Connection, name: str = "biblical_transmission") -> dict[str, int]:
    base = corpus_dir() / name
    refs = json.loads((base / "references.json").read_text(encoding="utf-8"))
    know = json.loads((base / "knowledge.json").read_text(encoding="utf-8"))
    for lic in refs["licenses"]:
        conn.execute(
            """insert into public.licenses (code, name, url, allows_display, allows_excerpt, allows_full_text,
                 allows_derivatives, requires_attribution) values (%(code)s,%(name)s,%(url)s,%(allows_display)s,
                 %(allows_excerpt)s,%(allows_full_text)s,%(allows_derivatives)s,%(requires_attribution)s)
               on conflict (code) do nothing""", lic)
    ref_ids: dict[str, str] = {}
    for r in refs["references"]:
        row = conn.execute(
            """insert into public.bibliographic_references (slug, ref_type, authors, title, container_title, publisher, year,
                 edition, language, identifiers) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               on conflict (slug) do update set title=excluded.title returning id""",
            (r["slug"], r["ref_type"], r["authors"], r["title"], r.get("container_title"), r.get("publisher"), r.get("year"),
             r.get("edition"), r.get("language"), json.dumps(r.get("identifiers", {})))).fetchone()
        ref_ids[r["slug"]] = str(row["id"])

    topic_ids = seed_topics(conn)
    topic_id = topic_ids[know["topic"]]
    doc_ids: dict[str, str] = {}
    for d in refs["documents"]:
        existing = conn.execute("select id from public.documents where slug=%s", (d["slug"],)).fetchone()
        if existing:
            doc_ids[d["slug"]] = str(existing["id"])
            continue
        body = (base / d["file"]).read_text(encoding="utf-8")
        try:
            res = ingest_document(conn, DocumentInput(
                slug=d["slug"], title=d["title"], body=body, doc_kind="editorial_note", license_code="CC-BY-4.0",
                authors=["Equipo editorial de Ciencia y Dios"], institution="Ciencia y Dios", language="es",
                rights_statement="Nota editorial original del proyecto, CC BY 4.0. Resume fuentes secundarias citadas.",
                provenance={"origin": "corpus/" + name + "/" + d["file"], "method": "redacción editorial",
                            "review": "pendiente de revisión por especialista"},
                visibility="public", review_status="pending_review",
                cites=[ref_ids[c] for c in d["cites"]]), owner_id=None)
            doc_ids[d["slug"]] = res["id"]
        except DuplicateDocument as e:
            doc_ids[d["slug"]] = e.existing_id

    place_ids: dict[str, str] = {}
    for p in know["places"]:
        row = conn.execute(
            """insert into public.entities (slug, kind, name, attributes, topic_id) values (%s,'place',%s,%s,%s)
               on conflict (slug) do update set name=excluded.name, attributes=excluded.attributes returning id""",
            ("lugar-" + p["slug"], p["name"], json.dumps({"lat": p["lat"], "lon": p["lon"]}), topic_id)).fetchone()
        place_ids[p["slug"]] = str(row["id"])

    n_claims = n_ev = 0
    for c in know["claims"]:
        if conn.execute("select 1 from public.claims where slug=%s", (c["slug"],)).fetchone():
            continue
        kind = {"printed_book": "edition", "critical_edition": "edition"}.get(c.get("illustration", ""), "manuscript")
        subj = conn.execute(
            """insert into public.entities (slug, kind, name, description, attributes, topic_id) values (%s,%s,%s,%s,%s,%s)
               on conflict (slug) do update set name=excluded.name returning id""",
            ("ent-" + c["slug"], kind, c["title"], c["statement"], json.dumps({"illustration": c.get("illustration")}),
             topic_id)).fetchone()["id"]
        place = place_ids.get(c["place"]) if c.get("place") else None
        is_event = c.get("is_event", True) and c.get("date_start") is not None
        claim_id = conn.execute(
            """insert into public.claims (slug, topic_id, statement, asserted_by, discipline, category, is_event, date_start,
                 date_end, date_precision, date_label, place_entity_id, subject_entity_id, consensus_note,
                 insufficient_evidence_note, future_research_note, review_status, visibility, content_sha256)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending_review','public',%s) returning id""",
            (c["slug"], topic_id, c["statement"], c["asserted_by"], c["discipline"], c["category"], is_event,
             c.get("date_start"), c.get("date_end"), c.get("date_precision", "unknown"), c.get("date_label", ""), place, subj,
             c.get("consensus_note", ""), c.get("insufficient_evidence_note", ""), c.get("future_research_note", ""),
             sha(c["statement"]))).fetchone()["id"]
        if place:
            conn.execute("""insert into public.entity_relations (subject_id, predicate, object_id, evidence_claim_id)
                            values (%s,'produced_at',%s,%s) on conflict do nothing""", (subj, place, claim_id))
        n_claims += 1
        ev_by_stance: dict[str, list[str]] = {}
        for ev in c["evidence"]:
            ch = _find_chunk(conn, doc_ids[ev["doc"]], ev["fragment"])
            eid = conn.execute(
                """insert into public.evidence_links (claim_id, chunk_id, reference_id, stance, exact_fragment, locator)
                   values (%s,%s,%s,%s,%s,%s) returning id""",
                (claim_id, ch["id"], ref_ids.get(ev["ref"]) if ev.get("ref") else None, ev["stance"], ev["fragment"],
                 ch["locator"])).fetchone()["id"]
            ev_by_stance.setdefault(ev["stance"], []).append(str(eid))
            n_ev += 1
        for i, p in enumerate(c.get("perspectives", [])):
            linked = ev_by_stance.get("supports" if i == 0 else "challenges", []) or ev_by_stance.get("qualifies", [])
            conn.execute(
                """insert into public.perspectives (claim_id, label, tradition, summary, held_by, evidence_link_ids)
                   values (%s,%s,%s,%s,%s,%s::uuid[])""",
                (claim_id, p["label"], p["tradition"], p["summary"], p.get("held_by", ""), linked))
    conn.execute(
        """update public.topics set content_status='seeded', open_questions=%s where id=%s""",
        (["¿Qué significa reconstruir un «texto original» en libros con varias ediciones literarias?",
          "¿Cuál es la fecha precisa de los papiros más antiguos del Nuevo Testamento?",
          "¿Qué relación exacta hubo entre el asentamiento de Qumrán, las cuevas y los manuscritos?"], topic_id))
    return {"claims": n_claims, "evidence": n_ev, "documents": len(doc_ids)}


def run(dev_users: bool = False) -> dict[str, Any]:
    with service_tx() as conn:
        seed_agents(conn)
        seed_budgets(conn)
        if dev_users:
            seed_dev_users(conn)
        stats = seed_corpus(conn)
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev-users", action="store_true")
    try:
        print(run(ap.parse_args().dev_users))
    finally:
        from .db import close_pool
        close_pool()
