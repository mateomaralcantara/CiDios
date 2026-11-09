"""Conectores probados con respuestas simuladas (este entorno no tiene salida a api.openalex.org ni api.crossref.org)."""
from __future__ import annotations

import httpx

from cdd.connectors.crossref import CrossrefConnector
from cdd.connectors.openalex import OpenAlexConnector


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_openalex_parsing():
    def h(req):
        assert req.url.path == "/works" and req.url.params["search"] == "codex sinaiticus"
        return httpx.Response(200, json={"results": [{
            "id": "https://openalex.org/W1", "display_name": "A study", "publication_year": 2010,
            "ids": {"doi": "https://doi.org/10.1/x", "openalex": "https://openalex.org/W1"},
            "authorships": [{"author": {"display_name": "Ana Pérez"}}],
            "open_access": {"oa_url": None}, "primary_location": {"source": {"display_name": "Journal"}, "license": None}}]})
    rep = OpenAlexConnector(_client(h)).search("codex sinaiticus")
    assert rep.ok and rep.candidates[0].authors == ["Ana Pérez"] and rep.candidates[0].identifiers["doi"]


def test_crossref_parsing():
    def h(req):
        return httpx.Response(200, json={"message": {"items": [{
            "DOI": "10.1/y", "title": ["Papyri"], "author": [{"given": "B.", "family": "N."}],
            "issued": {"date-parts": [[2005, 1]]}, "container-title": ["HTR"]}]}})
    rep = CrossrefConnector(_client(h)).search("P52")
    assert rep.ok and rep.candidates[0].year == 2005 and rep.candidates[0].identifiers == {"doi": "10.1/y"}


def test_connector_failure_is_reported_not_hidden():
    rep = OpenAlexConnector(_client(lambda req: httpx.Response(503))).search("x")
    assert not rep.ok and "503" in rep.error and rep.candidates == []
