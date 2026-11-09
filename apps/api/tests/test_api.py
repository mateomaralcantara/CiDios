"""API HTTP de extremo a extremo (incluye progreso educativo y centro de control)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cdd.harness import engine
from cdd.main import app

from .conftest import FINAL_PROMPT


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def tok(client, who):
    r = client.post("/v1/auth/dev-token", json={"user": who})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def run(client):
    h = tok(client, "user")
    r = client.post("/v1/investigations", json={"prompt": FINAL_PROMPT, "force_new": True}, headers=h)
    assert r.status_code == 201, r.text
    run_id = r.json()["run_id"]
    assert engine.process_run(run_id) == "READY"   # el worker está desactivado en pruebas; se ejecuta igual que en producción
    detail = client.get(f"/v1/runs/{run_id}", headers=h).json()
    return {"run_id": run_id, "experience_id": detail["run"]["result"]["experience_id"]}


def test_health_and_auth(client):
    assert client.get("/v1/health").json()["status"] == "ok"
    assert client.get("/v1/me").json()["role"] == "anon"
    assert client.get("/v1/me", headers=tok(client, "owner")).json()["role"] == "owner"
    assert client.get("/v1/me", headers={"Authorization": "Bearer basura"}).status_code == 401


def test_forged_token_rejected(client):
    import jwt
    forged = jwt.encode({"sub": "00000000-0000-4000-8000-000000000001", "aud": "authenticated", "iss": "cdd-dev"},
                        "otro-secreto-cualquiera-de-32-caracteres", algorithm="HS256")
    assert client.get("/v1/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_encyclopedia_article_and_comparator(client):
    topics = client.get("/v1/topics").json()
    assert len(topics) == 20
    bible = next(t for t in topics if t["slug"] == "biblia-manuscritos-critica-textual")
    assert bible["claims"] == 29 and bible["content_status"] == "seeded"
    assert all(t["content_status"] == "empty" for t in topics if t["slug"] != bible["slug"])
    art = client.get("/v1/topics/biblia-manuscritos-critica-textual").json()
    assert len(art["claims"]) == 29 and len(art["bibliography"]) >= 10
    assert all(c["evidence"] for c in art["claims"])
    cmp_ = client.get("/v1/topics/biblia-manuscritos-critica-textual/compare").json()
    assert any(r["challenging_evidence"] for r in cmp_["rows"])


def test_library_search_and_upload(client):
    res = client.get("/v1/library/search", params={"q": "colofón del Códice de Leningrado"}).json()
    assert res["results"][0]["locator"] == "Códice de Leningrado"
    h = tok(client, "user2")
    up = client.post("/v1/library/documents", headers=h, json={
        "title": "Mis apuntes", "rights_statement": "Texto propio",
        "body": "## Notas\n\nApuntes personales sobre el palimpsesto imaginario de Vilanova para mi curso."})
    assert up.status_code == 201
    assert client.post("/v1/library/documents", headers=h, json={
        "title": "Restringido", "rights_statement": "N/A", "license_code": "NO-EXCERPT",
        "body": "## Notas\n\nTexto con licencia que no permite almacenar extractos en la biblioteca."}).status_code == 422
    doc_id = up.json()["id"]
    assert all(r["document_id"] != doc_id for r in client.get("/v1/library/search", params={"q": "palimpsesto Vilanova"}).json()["results"])
    assert all(r["document_id"] != doc_id for r in client.get("/v1/library/search", params={"q": "palimpsesto Vilanova"},
                                                               headers=tok(client, "user")).json()["results"])
    mine = client.get("/v1/library/search", params={"q": "palimpsesto Vilanova"}, headers=h).json()["results"]
    assert mine[0]["document_id"] == doc_id


def test_run_detail_events_and_stream(client, run):
    h = tok(client, "user")
    d = client.get(f"/v1/runs/{run['run_id']}", headers=h).json()
    assert d["run"]["state"] == "READY" and len(d["tasks"]) == 13 and d["checkpoints"]
    assert d["costs"]
    ev = client.get(f"/v1/runs/{run['run_id']}/events", headers=h).json()
    assert any(e["event_type"] == "state_change" for e in ev)
    with client.stream("GET", f"/v1/runs/{run['run_id']}/stream", headers=h) as s:
        body = "".join(s.iter_text())
    assert "event: harness" in body and '"READY"' in body
    assert client.get(f"/v1/runs/{run['run_id']}", headers=tok(client, "user2")).status_code == 404


def test_missions_progress_is_graded_server_side_and_persisted(client, run):
    h = tok(client, "user")
    exp = client.get(f"/v1/experiences/{run['experience_id']}", headers=h).json()
    stages = exp["experience_spec"]["stages"]
    # etapa 2 bloqueada al inicio
    m2 = stages[1]["mission"]
    assert client.post(f"/v1/experiences/{run['experience_id']}/missions", headers=h,
                       json={"mission_id": m2["id"], "answers": {}}).status_code == 409
    m1 = stages[0]["mission"]
    wrong = {q["id"]: (q["correct_index"] + 1) % len(q["options"]) for q in m1["questions"]}
    r = client.post(f"/v1/experiences/{run['experience_id']}/missions", headers=h,
                    json={"mission_id": m1["id"], "answers": wrong}).json()
    assert r["passed"] is False and r["progress"]["unlocked_stage"] == 0
    assert all(f["explanation"] for f in r["feedback"])
    right = {q["id"]: q["correct_index"] for q in m1["questions"]}
    r = client.post(f"/v1/experiences/{run['experience_id']}/missions", headers=h,
                    json={"mission_id": m1["id"], "answers": right}).json()
    assert r["passed"] and r["progress"]["unlocked_stage"] == 1
    # completar todas
    for st in stages[1:]:
        ans = {q["id"]: q["correct_index"] for q in st["mission"]["questions"]}
        assert client.post(f"/v1/experiences/{run['experience_id']}/missions", headers=h,
                           json={"mission_id": st["mission"]["id"], "answers": ans}).json()["passed"]
    prog = client.get(f"/v1/experiences/{run['experience_id']}/progress", headers=h).json()
    assert len(prog["completed_missions"]) == len(stages) and prog["score"] > 0
    # otro usuario no ve ni el borrador ni el progreso
    assert client.get(f"/v1/experiences/{run['experience_id']}", headers=tok(client, "user2")).status_code == 404


def test_export_contains_references(client, run):
    h = tok(client, "user")
    md = client.get(f"/v1/experiences/{run['experience_id']}/export", params={"format": "markdown"}, headers=h).text
    assert "## Referencias" in md and "Textual Criticism of the Hebrew Bible" in md and "## Incertidumbres" in md
    js = client.get(f"/v1/experiences/{run['experience_id']}/export", headers=h).json()
    assert js["knowledge_packet"]["sha256"]


def test_admin_requires_owner(client):
    for path in ("/v1/admin/overview", "/v1/admin/agents", "/v1/admin/runs", "/v1/admin/costs", "/v1/admin/providers"):
        assert client.get(path).status_code == 401
        assert client.get(path, headers=tok(client, "user")).status_code == 403
        assert client.get(path, headers=tok(client, "owner")).status_code == 200


def test_admin_controls(client, run):
    o = tok(client, "owner")
    agents = client.get("/v1/admin/agents", headers=o).json()
    assert len(agents) == 40 and sum(a["status"] == "operational" for a in agents) == 9
    assert client.patch("/v1/admin/agents/logic_analyst", headers=o, json={"enabled": True}).status_code == 409
    assert client.patch("/v1/admin/agents/timeline_director", headers=o, json={"max_cost_per_run_usd": 2}).status_code == 200
    prov = client.get("/v1/admin/providers", headers=o).json()
    assert all("key" not in k or "…" in str(v) or v == "" for m in prov["models"] for k, v in m.items() if k == "key_hint")
    assert client.put("/v1/admin/budgets", headers=o, json={"scope": "provider", "scope_ref": "anthropic",
                                                             "period": "monthly", "limit_usd": 50}).status_code == 200
    assert client.get("/v1/admin/quality", headers=o).json()["evidence"]
    ov = client.get("/v1/admin/overview", headers=o).json()
    assert ov["agents"]["operational"] == 9 and ov["library"]["claims"] == 29


def test_publish_flow(client, run):
    assert client.post(f"/v1/runs/{run['run_id']}/publish", headers=tok(client, "user")).status_code == 403
    r = client.post(f"/v1/runs/{run['run_id']}/publish", headers=tok(client, "owner"))
    assert r.status_code == 200 and r.json()["state"] == "PUBLISHED"
    # publicado: visible para visitantes y otros usuarios
    assert client.get(f"/v1/experiences/{run['experience_id']}").status_code == 200
    assert client.get(f"/v1/experiences/{run['experience_id']}", headers=tok(client, "user2")).status_code == 200
    assert client.post(f"/v1/runs/{run['run_id']}/publish", headers=tok(client, "owner")).status_code == 409


def test_user_cannot_control_others_runs(client, run):
    assert client.post(f"/v1/runs/{run['run_id']}/cancel", headers=tok(client, "user2")).status_code == 404
    assert client.post(f"/v1/runs/{run['run_id']}/approve", headers=tok(client, "user")).status_code == 403
