from __future__ import annotations

from .base import Connector
from .crossref import CrossrefConnector
from .openalex import OpenAlexConnector

CONNECTORS: dict[str, type[Connector]] = {"openalex": OpenAlexConnector, "crossref": CrossrefConnector}
# Diseñados, no implementados todavía (ver docs/SOURCES.md): pubmed, europepmc, arxiv, sep, nasa_ads, museums...
PLANNED = ["pubmed", "europepmc", "arxiv", "stanford_encyclopedia", "nasa_ads", "esa", "institutional_repositories",
           "museum_archives", "manuscript_collections", "digital_libraries"]
