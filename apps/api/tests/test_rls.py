"""RLS: propietario, usuario regular, visitante y accesos cruzados."""
from __future__ import annotations

import psycopg
import pytest

from cdd.db import service_tx, user_tx
from cdd.library.ingest import DocumentInput, ingest_document
from cdd.library.search import search

from .conftest import principal

ANON = None


def claims(name):
    return principal(name).claims


def count(c, sql, args=()):
    return c.execute(sql, args).fetchone()["n"]


@pytest.fixture(scope="module")
def private_doc():
    with user_tx(claims("user")) as c:
        res = ingest_document(c, DocumentInput(
            title="Notas privadas de usuario", doc_kind="user_upload", license_code="USER-PRIVATE",
            body="## Apuntes\n\nContenido confidencial sobre zarzamoras cuánticas del archivo personal.",
            rights_statement="Mío"), owner_id=principal("user").user_id)
    return res["id"]


def test_anon_reads_public_catalog():
    with user_tx(ANON) as c:
        assert count(c, "select count(*) n from public.claims where origin = 'curated'") == 29
        assert count(c, "select count(*) n from public.documents where slug like 'nota-%%'") == 5
        assert count(c, "select count(*) n from public.documents where visibility='private'") == 0
        assert count(c, "select count(*) n from public.evidence_links e join public.claims c on c.id = e.claim_id where c.origin = 'curated'") == 57


@pytest.mark.parametrize("table", ["investigations", "harness_runs", "harness_events", "cost_ledger",
                                   "learning_progress", "budget_policies", "profiles", "user_roles", "agent_definitions"])
def test_anon_cannot_read_private_tables(table):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with user_tx(ANON) as c:
            c.execute(f"select * from public.{table} limit 1")


def test_anon_cannot_write():
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with user_tx(ANON) as c:
            c.execute("insert into public.topics (slug, title) values ('x','x')")


def test_user_cannot_escalate_role():
    uid = principal("user").user_id
    with user_tx(claims("user")) as c:
        assert c.execute("update public.user_roles set role='owner' where user_id=%s", (uid,)).rowcount == 0
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with user_tx(claims("user")) as c:
            c.execute("insert into public.user_roles (user_id, role) values (%s,'owner') on conflict (user_id) do update set role='owner'",
                      (uid,))
    with service_tx() as c:
        assert c.execute("select role::text from public.user_roles where user_id=%s", (uid,)).fetchone()["role"] == "user"


def test_user_cannot_publish_public_document():
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with user_tx(claims("user")) as c:
            ingest_document(c, DocumentInput(title="Falso público", doc_kind="user_upload", license_code="USER-PRIVATE",
                                             body="## X\n\nIntento de publicar un documento público sin revisión editorial.",
                                             visibility="public"), owner_id=principal("user").user_id)


def test_user_cannot_modify_claims_or_evidence():
    with user_tx(claims("user")) as c:
        assert c.execute("update public.claims set statement='alterada'").rowcount == 0
        assert c.execute("delete from public.evidence_links").rowcount == 0


def test_cross_user_private_document_isolation(private_doc):
    with user_tx(claims("user")) as c:
        assert count(c, "select count(*) n from public.documents where id=%s", (private_doc,)) == 1
        assert any(r["document_id"] == private_doc for r in search(c, "zarzamoras cuánticas", 5, "text"))
    for other in (ANON, claims("user2")):
        with user_tx(other) as c:
            assert count(c, "select count(*) n from public.documents where id=%s", (private_doc,)) == 0
            assert count(c, "select count(*) n from public.document_chunks where document_id=%s", (private_doc,)) == 0
            assert not any(r["document_id"] == private_doc for r in search(c, "zarzamoras cuánticas", 5, "text"))
    with user_tx(claims("owner")) as c:
        assert count(c, "select count(*) n from public.documents where id=%s", (private_doc,)) == 1


def test_user2_cannot_tamper_with_user_document(private_doc):
    with user_tx(claims("user2")) as c:
        assert c.execute("update public.documents set title='hackeado' where id=%s", (private_doc,)).rowcount == 0
        assert c.execute("delete from public.documents where id=%s", (private_doc,)).rowcount == 0


def test_fabricated_citation_rejected_by_database():
    with service_tx() as c:
        chunk = c.execute("select id from public.document_chunks limit 1").fetchone()["id"]
        claim = c.execute("select id from public.claims limit 1").fetchone()["id"]
    with pytest.raises(psycopg.errors.CheckViolation):
        with service_tx() as c:
            c.execute("""insert into public.evidence_links (claim_id, chunk_id, stance, exact_fragment)
                         values (%s,%s,'supports','Un texto que ninguna fuente contiene')""", (claim, chunk))


def test_service_role_secret_not_needed_for_reads():
    """El cliente nunca necesita credenciales administrativas para leer el catálogo público."""
    with user_tx(ANON) as c:
        assert c.execute("select current_user as u").fetchone()["u"] == "anon"


def test_new_auth_user_gets_profile_and_user_role():
    uid = "00000000-0000-4000-8000-0000000000aa"
    with service_tx() as c:
        c.execute("insert into auth.users (id, email) values (%s, 'nueva@example.org')", (uid,))
        row = c.execute("""select p.display_name, r.role::text as role from public.profiles p
                           join public.user_roles r on r.user_id=p.id where p.id=%s""", (uid,)).fetchone()
    assert row == {"display_name": "nueva", "role": "user"}
