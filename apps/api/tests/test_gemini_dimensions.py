"""Gemini + 3 dimensiones de búsqueda + HARNESS de bibliografía, con servicios externos simulados."""
from __future__ import annotations

import json
import re

import httpx
import pytest

from cdd import net
from cdd.config import get_settings
from cdd.db import service_tx
from cdd.experience.contracts import KnowledgePacket
from cdd.harness import engine
from cdd.providers.gemini import GeminiClient, GeminiError

QUESTION = "Según la cosmología, ¿qué evidencia hay de la inflación cósmica en el fondo cósmico de microondas?"
ABS = {
    "W1": "Measurements of the cosmic microwave background temperature anisotropies show a nearly scale invariant spectrum "
          "of primordial fluctuations, which is a key prediction of cosmic inflation models and constitutes evidence supporting them.",
    "W2": "We report a detection of primordial B-mode polarization in the cosmic microwave background attributed to "
          "gravitational waves from cosmic inflation, providing direct evidence of the inflationary epoch in the early universe.",
    "W3": "Inflation remains the leading paradigm for the early universe, yet alternative scenarios can reproduce several "
          "cosmic microwave background observations, so the evidence for inflation should be considered strong but not conclusive.",
}


def inv(text):
    d = {}
    for i, w in enumerate(text.split()):
        d.setdefault(w, []).append(i)
    return d


def work(wid, author_ids):
    return {"id": f"https://openalex.org/{wid}", "display_name": f"Inflation and the CMB ({wid})", "publication_year": 2015,
            "type": "article", "doi": f"https://doi.org/10.1/{wid.lower()}", "abstract_inverted_index": inv(ABS[wid]),
            "authorships": [{"author": {"id": f"https://openalex.org/{a}", "display_name": f"Autor {a}"}, "institutions": []}
                            for a in author_ids],
            "cited_by_count": 100, "is_retracted": False, "open_access": {"is_oa": True},
            "primary_location": {"source": {"display_name": "Physical Review", "type": "journal"}}}


class Calls:
    gemini = 0
    prompts: list[str] = []


def gemini_reply(body):
    Calls.gemini += 1
    schema = body["generationConfig"]["responseSchema"]
    text = body["contents"][0]["parts"][0]["text"]
    Calls.prompts.append(text)
    if "queries_en" in schema["properties"]:
        data = {"queries_en": ["cosmic inflation microwave background evidence"], "queries_es": ["inflación cósmica evidencia"]}
    else:
        docs = re.findall(r'<document id="(C\d+)" trust="untrusted-data">\n\[(.*?)\]\n(.*?)\n</document>', text, re.S)
        resumen = {(m := re.search(r"\((W\d)\)", h)) and m.group(1): (cid, body_) for cid, h, body_ in docs if "sección: Resumen" in h}
        def q(w, n=14):
            cid, b = resumen[w]
            return cid, " ".join(b.split()[:n])
        c1, q1 = q("W1")
        c2, q2 = q("W2")
        c3, q3 = q("W3")
        data = {"unanswered": "", "claims": [
            {"statement": "El espectro casi invariante de escala de las fluctuaciones primordiales es una predicción clave de la inflación.",
             "category": "scholarly_consensus", "discipline": "Cosmología", "asserted_by": "Autores de W1", "is_event": False,
             "date_precision": "unknown", "evidence": [{"chunk": c1, "quote": q1, "stance": "supports"},
                                                       {"chunk": c3, "quote": q3, "stance": "qualifies"}]},
            {"statement": "Se detectaron modos B primordiales debidos a ondas gravitacionales de la inflación.",
             "category": "empirical_fact", "discipline": "Cosmología", "asserted_by": "Autores de W2", "is_event": False,
             "date_precision": "unknown", "evidence": [{"chunk": c2, "quote": q2, "stance": "supports"}]},
            {"statement": "La inflación está demostrada sin ninguna duda.", "category": "empirical_fact", "discipline": "Cosmología",
             "asserted_by": "Nadie", "is_event": False, "date_precision": "unknown",
             "evidence": [{"chunk": c1, "quote": "the inflation is proven beyond any doubt by all observations", "stance": "supports"}]},
            {"statement": "La inflación es el paradigma principal, aunque hay escenarios alternativos.", "category": "contested",
             "discipline": "Cosmología", "asserted_by": "Autor experto A1", "is_event": False, "date_precision": "unknown",
             "evidence": [{"chunk": c3, "quote": q3, "stance": "supports"}]},
        ]}
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(data)}]}, "finishReason": "STOP"}],
                                     "usageMetadata": {"promptTokenCount": 2000, "candidatesTokenCount": 500, "thoughtsTokenCount": 100},
                                     "modelVersion": "gemini-2.5-flash"})


def handler(req: httpx.Request) -> httpx.Response:
    host, path = req.url.host, req.url.path
    if host == "generativelanguage.googleapis.com":
        assert req.headers["x-goog-api-key"] == "clave-de-prueba"
        return gemini_reply(json.loads(req.content))
    if host == "api.openalex.org":
        assert req.headers.get("authorization") == "Bearer oa-key"
        if path == "/works" and "author.id:A1" in req.url.params.get("filter", ""):
            return httpx.Response(200, json={"results": [work("W3", ["A1"])]})
        if path == "/works":
            return httpx.Response(200, json={"results": [work("W1", ["A1", "A2"]), work("W2", ["A2"])]})
        if path.startswith("/authors/"):
            aid = path.rsplit("/", 1)[-1]
            return httpx.Response(200, json={"id": f"https://openalex.org/{aid}", "display_name": f"Autor {aid}",
                                             "summary_stats": {"h_index": 40 if aid == "A1" else 5}, "works_count": 200,
                                             "cited_by_count": 9000, "last_known_institutions": [{"display_name": "Uni X"}]})
    if host == "api.crossref.org":
        if path == "/works":
            return httpx.Response(200, json={"message": {"items": []}})
        doi = path.split("/works/", 1)[1]
        item = {"DOI": doi, "type": "journal-article", "title": ["x"], "issued": {"date-parts": [[2015]]},
                "container-title": ["Physical Review"]}
        if doi.endswith("w2"):
            item["updated-by"] = [{"type": "retraction", "DOI": "10.1/notice"}]
        return httpx.Response(200, json={"message": item})
    return httpx.Response(404)


@pytest.fixture
def external(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "gemini_api_key", "clave-de-prueba")
    monkeypatch.setattr(s, "openalex_api_key", "oa-key")
    monkeypatch.setattr(s, "connectors_enabled", ["openalex", "crossref"])
    monkeypatch.setattr(s, "experts_min_h_index", 15)
    monkeypatch.setattr(net, "TRANSPORT", httpx.MockTransport(handler))
    Calls.gemini, Calls.prompts = 0, []
    yield


def test_gemini_client_parses_json_and_cost(external):
    res = GeminiClient().generate_json("sys", "hola", {"type": "OBJECT", "properties": {
        "queries_en": {"type": "ARRAY", "items": {"type": "STRING"}}}, "required": ["queries_en"]})
    assert res.data["queries_en"] and res.input_tokens == 2000 and res.output_tokens == 600
    assert res.usd == pytest.approx(2000 / 1e6 * 0.30 + 600 / 1e6 * 2.50)


@pytest.mark.parametrize("status, text", [(403, "rechazó la clave"), (404, "no existe"), (400, "Error de Gemini")])
def test_gemini_errors_are_explained(monkeypatch, status, text):
    s = get_settings()
    monkeypatch.setattr(s, "gemini_api_key", "k")
    monkeypatch.setattr(net, "TRANSPORT", httpx.MockTransport(lambda r: httpx.Response(status, json={"error": {"message": "x"}})))
    with pytest.raises(GeminiError, match=text):
        GeminiClient().generate_json("s", "p", {"type": "OBJECT"})


def test_three_dimensions_llm_and_bibliography_harness(external, user):
    r = engine.create_investigation(user, QUESTION, force_new=True)
    assert engine.process_run(r["run_id"]) == "READY"
    with service_tx() as c:
        tasks = {t["task_key"]: t for t in c.execute("select task_key, agent_code, status::text as status, output from public.harness_tasks "
                                                      "where run_id=%s", (r["run_id"],)).fetchall()}
        exp = c.execute("select knowledge_packet from public.experiences where run_id=%s", (r["run_id"],)).fetchone()
        ledger = c.execute("select * from public.cost_ledger where run_id=%s and provider='gemini'", (r["run_id"],)).fetchall()
        spent = c.execute("select spent_usd from public.harness_runs where id=%s", (r["run_id"],)).fetchone()["spent_usd"]
    # plan: dimensiones 1 y 2, especialista de cosmología con Gemini y HARNESS de bibliografía
    assert tasks["extract"]["agent_code"] == "cosmologist"
    assert all(tasks[k]["status"] == "succeeded" for k in ("acquire_published", "acquire_experts", "extract", "bibliography"))
    d1, d2 = tasks["acquire_published"]["output"], tasks["acquire_experts"]["output"]
    assert len(d1["documents"]) == 2 and d1["queries"][0] == "cosmic inflation microwave background evidence"
    assert [e["name"] for e in d2["experts"]] == ["Autor A1"] and d2["documents"][0]["tier"] == "expert_peer_reviewed"
    # Gemini: la cita inventada se descarta
    ex = tasks["extract"]["output"]
    assert ex["proposed"] == 4 and ex["accepted"] == 3
    assert any("no literal" in b["reason"] for d in ex["dropped"] for b in d.get("bad_evidence", []))
    # HARNESS de bibliografía: W2 retractada excluida, DOI resueltos
    bib = tasks["bibliography"]["output"]
    assert [s["stage"] for s in bib["stages"]] == ["COLLECT", "RESOLVE", "AUDIT", "CLASSIFY", "FORMAT", "BIND", "REPORT"]
    assert bib["metrics"]["evidence_excluded_retracted"] == 1 and bib["metrics"]["doi_resolved"] >= 2
    packet = KnowledgePacket.model_validate(exp["knowledge_packet"])
    statements = [c.statement for c in packet.claims]
    assert not any("modos B" in s for s in statements)              # solo la obra retractada la respaldaba
    assert not any("demostrada sin ninguna duda" in s for s in statements)
    assert all(c.origin == "llm_extracted" and c.review_status == "pending_review" for c in packet.claims)
    assert {b.tier for b in packet.bibliography} == {"peer_reviewed", "expert_peer_reviewed"}
    assert all(b.doi and "https://doi.org/" in b.apa and not b.retracted for b in packet.bibliography)
    assert all(e.citation_key in {b.key for b in packet.bibliography} for c in packet.claims for e in c.evidence)
    assert packet.dimensions["experts"]["experts"][0]["h_index"] == 40 and packet.dimensions["llm"]["accepted"] == 3
    assert packet.bibliography_metrics["claims_with_expert_support_pct"] == 50.0
    assert packet.bibliography_metrics["claims_with_peer_reviewed_support_pct"] == 100.0
    # costes reales de Gemini en el libro de costes
    assert len(ledger) == 2 and all(row["input_tokens"] == 2000 and row["output_tokens"] == 600 for row in ledger)
    assert float(spent) == pytest.approx(2 * (2000 / 1e6 * 0.30 + 600 / 1e6 * 2.50), abs=1e-5)
    # los documentos se entregan al modelo como datos no confiables
    assert all('trust="untrusted-data"' in p for p in Calls.prompts[1:])


def test_llm_claims_are_private_to_the_author(external, user, user2):
    r = engine.create_investigation(user, QUESTION + " (privacidad)", force_new=True)
    assert engine.process_run(r["run_id"]) == "READY"
    from cdd.db import user_tx
    with user_tx(user2.claims) as c:
        assert c.execute("select count(*) n from public.claims where run_id=%s", (r["run_id"],)).fetchone()["n"] == 0
    with user_tx(user.claims) as c:
        assert c.execute("select count(*) n from public.claims where run_id=%s", (r["run_id"],)).fetchone()["n"] == 3


def test_without_gemini_key_the_plan_stays_deterministic(user, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "gemini_api_key", "")
    monkeypatch.setattr(s, "connectors_enabled", [])
    r = engine.create_investigation(user, "Investiga el Códice de Alepo y su fecha", force_new=True)
    assert engine.process_run(r["run_id"]) == "READY"
    with service_tx() as c:
        keys = {t["task_key"] for t in c.execute("select task_key from public.harness_tasks where run_id=%s", (r["run_id"],))}
    assert "extract" not in keys and "acquire_published" not in keys and "bibliography" in keys


def test_pasted_key_with_newline_is_cleaned(monkeypatch):
    """Una clave pegada en Render con salto de línea o comillas provocaba LocalProtocolError en httpx."""
    from cdd.config import Settings
    monkeypatch.setenv("CDD_GEMINI_API_KEY", ' "AIzaFAKEKEY123"\n')
    monkeypatch.setenv("CDD_GEMINI_MODEL", "gemini-test \n")
    s = Settings(_env_file=None)
    assert s.gemini_api_key == "AIzaFAKEKEY123" and s.gemini_model == "gemini-test"


def test_plan_queries_falls_back_when_gemini_fails(monkeypatch):
    from cdd.harness.agents import discovery
    from cdd.providers import gemini

    def boom(*a, **k):
        raise gemini.GeminiError("caída simulada")
    monkeypatch.setattr(gemini, "configured", lambda: True)
    monkeypatch.setattr(gemini.GeminiClient, "__init__", lambda self, *a, **k: None)
    monkeypatch.setattr(gemini.GeminiClient, "generate_json", boom)
    qs, usage = discovery.plan_queries("¿Qué dicen los manuscritos del mar Muerto sobre Isaías?", None)
    assert qs and usage == []


def test_broken_gemini_does_not_fail_the_investigation(external, user, monkeypatch):
    """Antes: «GeminiError: No se pudo contactar con Gemini: LocalProtocolError» → FAILED. Ahora sigue con fuentes verificadas."""
    from cdd.providers import gemini

    def broken(*a, **k):
        raise gemini.GeminiError("La clave CDD_GEMINI_API_KEY contiene caracteres no válidos")
    monkeypatch.setattr(gemini.GeminiClient, "generate_json", broken)
    r = engine.create_investigation(user, QUESTION + " (Gemini roto)", force_new=True)
    assert engine.process_run(r["run_id"]) in ("READY", "PARTIAL")
    with service_tx() as c:
        ex = c.execute("select status::text as status, output from public.harness_tasks where run_id=%s and task_key='extract'",
                       (r["run_id"],)).fetchone()
        warn = c.execute("select message from public.harness_events where run_id=%s and level='warning' and message like 'Gemini%%'",
                         (r["run_id"],)).fetchone()
    assert ex["status"] == "succeeded" and "caracteres no válidos" in ex["output"]["llm_error"]
    assert warn is not None
