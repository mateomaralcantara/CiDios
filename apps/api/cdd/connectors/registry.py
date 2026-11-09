from __future__ import annotations

from .arxiv import ArxivConnector
from .base import Connector
from .crossref import CrossrefConnector
from .europepmc import EuropePMCConnector
from .openalex import OpenAlexConnector

CONNECTORS: dict[str, type[Connector]] = {"openalex": OpenAlexConnector, "crossref": CrossrefConnector,
                                          "europepmc": EuropePMCConnector, "arxiv": ArxivConnector}
# Diseñados, no implementados todavía (ver docs/ROADMAP.md)
PLANNED = ["pubmed", "stanford_encyclopedia", "nasa_ads", "esa", "institutional_repositories",
           "museum_archives", "manuscript_collections", "digital_libraries"]

# Qué repositorios consultar según el área (dimensión 1). OpenAlex es transversal a todas.
AREA_SOURCES: dict[str, list[str]] = {
    "cosmologia-astrofisica": ["openalex", "arxiv", "crossref"],
    "fisica-fundamentos": ["openalex", "arxiv", "crossref"],
    "evolucion-origen-vida": ["openalex", "europepmc", "crossref"],
    "genetica-biologia-molecular": ["openalex", "europepmc", "crossref"],
    "neurociencia-conciencia": ["openalex", "europepmc", "arxiv"],
    "ia-mente-conciencia": ["openalex", "arxiv", "crossref"],
}
DEFAULT_SOURCES = ["openalex", "crossref"]


def sources_for(topic: str | None, enabled: list[str]) -> list[str]:
    wanted = AREA_SOURCES.get(topic or "", DEFAULT_SOURCES)
    return [s for s in wanted if s in enabled]
