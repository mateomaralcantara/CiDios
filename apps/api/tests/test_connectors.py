"""Conectores con respuestas simuladas (la forma de las respuestas se comprobó en vivo con Crossref, Europe PMC y arXiv)."""
from __future__ import annotations

import httpx

from cdd.connectors.arxiv import parse_feed
from cdd.connectors.crossref import CrossrefConnector
from cdd.connectors.europepmc import EuropePMCConnector
from cdd.connectors.openalex import OpenAlexConnector, abstract_from_index


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_openalex_parsing_and_abstract_reconstruction():
    assert abstract_from_index({"Hola": [0], "mundo": [1], "bello": [2]}) == "Hola mundo bello"

    def h(req):
        assert req.url.path == "/works" and "has_abstract:true" in req.url.params["filter"]
        return httpx.Response(200, json={"results": [{
            "id": "https://openalex.org/W1", "display_name": "A study", "publication_year": 2010, "type": "article",
            "doi": "https://doi.org/10.1/X", "abstract_inverted_index": {"Texto": [0], "del": [1], "resumen": [2]},
            "authorships": [{"author": {"id": "https://openalex.org/A1", "display_name": "Ana Pérez"}, "institutions": []}],
            "cited_by_count": 12, "is_retracted": False, "open_access": {"is_oa": True},
            "primary_location": {"source": {"display_name": "Journal", "type": "journal"}}}]})
    c = OpenAlexConnector(_client(h)).search("x").candidates[0]
    assert c.abstract == "Texto del resumen" and c.doi == "10.1/x" and c.tier == "peer_reviewed"
    assert c.authors[0].openalex_id == "https://openalex.org/A1"


def test_crossref_parsing_and_retraction_flag():
    def h(req):
        return httpx.Response(200, json={"message": {"items": [{
            "DOI": "10.1/Y", "type": "journal-article", "title": ["Papyri"], "author": [{"given": "B.", "family": "N."}],
            "issued": {"date-parts": [[2005, 1]]}, "container-title": ["HTR"], "abstract": "<jats:p>Resumen</jats:p>",
            "updated-by": [{"type": "retraction", "DOI": "10.1/z"}]}]}})
    c = CrossrefConnector(_client(h)).search("P52").candidates[0]
    assert c.year == 2005 and c.doi == "10.1/y" and c.abstract == "Resumen" and c.is_retracted and c.tier == "peer_reviewed"


def test_europepmc_parsing():
    def h(req):
        return httpx.Response(200, json={"resultList": {"result": [{
            "id": "1", "source": "MED", "title": "Consciousness", "abstractText": "<b>Abstract</b> text", "doi": "10.2/a",
            "pubYear": "2024", "journalInfo": {"journal": {"title": "Neuro"}}, "authorList": {"author": [{"fullName": "Doe J"}]},
            "citedByCount": 3, "isOpenAccess": "Y"}]}})
    c = EuropePMCConnector(_client(h)).search("x").candidates[0]
    assert c.abstract == "Abstract text" and c.venue == "Neuro" and c.tier == "peer_reviewed" and c.is_oa


def test_arxiv_feed_parsing():
    xml = """<?xml version='1.0'?><feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
      <entry><id>http://arxiv.org/abs/1</id><published>2014-01-01T00:00:00Z</published><title>Inflation</title>
      <summary>Text of the abstract.</summary><author><name>A. Linde</name></author></entry></feed>"""
    c = parse_feed(xml)[0]
    assert c.tier == "preprint" and c.year == 2014 and c.authors[0].name == "A. Linde"


def test_connector_failure_is_reported_not_hidden():
    rep = OpenAlexConnector(_client(lambda req: httpx.Response(503))).search("x")
    assert not rep.ok and "503" in rep.error and rep.candidates == []
