"""Embeddings de Gemini (simulados): ingesta, búsqueda por modelo, recálculo y respaldo local si Gemini falla."""
from __future__ import annotations

import json

import httpx
import pytest

from cdd import net
from cdd.config import get_settings
from cdd.db import service_tx, user_tx
from cdd.library.embeddings import GeminiEmbedder, HashingEmbedder, embed_documents
from cdd.library.ingest import DocumentInput, ingest_document
from cdd.library.search import search

H = HashingEmbedder()


def gemini_embed_handler(fail: bool = False):
    def h(req: httpx.Request) -> httpx.Response:
        if fail:
            return httpx.Response(429, json={"error": {"message": "quota"}})
        body = json.loads(req.content)
        assert req.url.path.endswith(":batchEmbedContents") and body["requests"][0]["outputDimensionality"] == 384
        # vectores «semánticos» simulados: reutiliza el embedder léxico para que la similitud tenga sentido
        return httpx.Response(200, json={"embeddings": [{"values": [x * 3 for x in H.embed(r["content"]["parts"][0]["text"])]}
                                                        for r in body["requests"]]})
    return h


@pytest.fixture
def gemini_embeddings(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "gemini_api_key", "k")
    monkeypatch.setattr(s, "embeddings_provider", "gemini")
    monkeypatch.setattr(net, "TRANSPORT", httpx.MockTransport(gemini_embed_handler()))
    return GeminiEmbedder().name


def test_ingest_and_search_use_gemini_model(gemini_embeddings):
    with service_tx() as c:
        res = ingest_document(c, DocumentInput(title="Documento vectorial", doc_kind="editorial_note", license_code="CC-BY-4.0",
                                               visibility="public", review_status="pending_review",
                                               body="## Astrolabio\n\nEl astrolabio medieval permitía calcular la altura de los astros."), None)
        model = c.execute("select distinct embedding_model from public.document_chunks where document_id=%s", (res["id"],)).fetchone()
    assert model["embedding_model"] == gemini_embeddings
    with user_tx(None) as c:
        hits = search(c, "astrolabio medieval altura de los astros", 5, "semantic")
    assert hits and hits[0]["document_title"] == "Documento vectorial"
    # los fragmentos con vectores del modelo local no se mezclan en la búsqueda semántica con Gemini
    with service_tx() as c:
        titles = {r["document_title"] for r in c.execute(
            "select d.title as document_title from public.document_chunks ch join public.documents d on d.id=ch.document_id "
            "where ch.id = any(%s::uuid[])", ([h["chunk_id"] for h in hits],)).fetchall()}
    assert "Los manuscritos del mar Muerto" not in titles


def test_gemini_failure_falls_back_to_local(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "gemini_api_key", "k")
    monkeypatch.setattr(s, "embeddings_provider", "gemini")
    monkeypatch.setattr(net, "TRANSPORT", httpx.MockTransport(gemini_embed_handler(fail=True)))
    vecs, model = embed_documents(["texto"])
    assert model == HashingEmbedder.name and len(vecs[0]) == 384


def test_reembed_dry_run_counts_pending(gemini_embeddings, capsys, monkeypatch):
    from cdd import reembed
    monkeypatch.setattr("sys.argv", ["reembed", "--dry-run"])
    assert reembed.main() == 0
    out = capsys.readouterr().out
    assert gemini_embeddings in out and "fragmentos por recalcular" in out
