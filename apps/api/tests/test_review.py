"""Revisión editorial: solo editor/propietario; aprobar publica, rechazar oculta, editar queda registrado."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cdd.db import service_tx, user_tx
from cdd.main import app

from .conftest import principal


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def tok(client, who):
    return {"Authorization": f"Bearer {client.post('/v1/auth/dev-token', json={'user': who}).json()['access_token']}"}


@pytest.fixture
def llm_claim():
    uid = principal("user").user_id
    with service_tx() as c:
        ch = c.execute("""select ch.id, ch.content from public.document_chunks ch join public.documents d on d.id=ch.document_id
                          where d.slug='nota-mar-muerto' order by ch.ordinal limit 1""").fetchone()
        frag = " ".join(ch["content"].split()[:10])
        cid = c.execute("""insert into public.claims (slug, statement, asserted_by, discipline, category, review_status, visibility,
                             content_sha256, created_by, origin, generated_by)
                           values (gen_random_uuid()::text, 'Afirmación propuesta por IA para revisar.', 'Gemini', 'Historia',
                             'historical_document', 'pending_review', 'private', 'x', %s, 'llm_extracted', '{"model":"gemini-test"}')
                           returning id""", (uid,)).fetchone()["id"]
        c.execute("insert into public.evidence_links (claim_id, chunk_id, stance, exact_fragment) values (%s,%s,'supports',%s)",
                  (cid, ch["id"], frag))
    return str(cid)


def anon_sees(cid):
    with user_tx(None) as c:
        return c.execute("select count(*) n from public.claims where id=%s", (cid,)).fetchone()["n"] == 1


def test_only_staff_can_review(client, llm_claim):
    assert client.get("/v1/review/claims").status_code == 401
    assert client.get("/v1/review/claims", headers=tok(client, "user")).status_code == 403
    assert client.post(f"/v1/review/claims/{llm_claim}", json={"action": "approve"}, headers=tok(client, "user")).status_code == 403
    q = client.get("/v1/review/claims", headers=tok(client, "owner")).json()
    item = next(c for c in q["claims"] if c["id"] == llm_claim)
    assert item["evidence"] and item["generated_by"]["model"] == "gemini-test"


def test_approve_publishes_and_records_history(client, llm_claim):
    assert not anon_sees(llm_claim)
    r = client.post(f"/v1/review/claims/{llm_claim}", json={"action": "approve", "note": "Cita correcta"}, headers=tok(client, "owner"))
    assert r.status_code == 200 and r.json()["review_status"] == "reviewed" and r.json()["history"][0]["action"] == "approve"
    assert anon_sees(llm_claim)


def test_edit_then_reject(client, llm_claim):
    o = tok(client, "owner")
    assert client.post(f"/v1/review/claims/{llm_claim}", json={"action": "edit"}, headers=o).status_code == 422
    assert client.post(f"/v1/review/claims/{llm_claim}", json={"action": "edit", "category": "no-existe"}, headers=o).status_code == 422
    r = client.post(f"/v1/review/claims/{llm_claim}", headers=o,
                    json={"action": "edit", "statement": "Afirmación corregida por el editor.", "category": "contested"})
    assert r.status_code == 200
    with service_tx() as c:
        row = c.execute("select statement, category::text, review_status::text from public.claims where id=%s", (llm_claim,)).fetchone()
        prev = c.execute("select previous from public.claim_reviews where claim_id=%s and action='edit'", (llm_claim,)).fetchone()
    assert row == {"statement": "Afirmación corregida por el editor.", "category": "contested", "review_status": "pending_review"}
    assert prev["previous"]["statement"] == "Afirmación propuesta por IA para revisar."
    r = client.post(f"/v1/review/claims/{llm_claim}", json={"action": "reject", "note": "No respaldada"}, headers=o)
    assert r.json()["review_status"] == "rejected" and not anon_sees(llm_claim)
