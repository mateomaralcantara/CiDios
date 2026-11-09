"""Conectores a repositorios bibliográficos autorizados (dimensiones 1 y 2).

Los conectores DESCUBREN obras y sus resúmenes con metadatos de procedencia. Un resumen solo se usa como
evidencia después de incorporarse a la biblioteca (licencia CITATION-ONLY), fragmentarse y verificarse
literalmente una cita contra él.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

import httpx

from ..net import http_client

# Niveles de procedencia, de mayor a menor peso probatorio dentro de la literatura académica
TIERS = ("expert_peer_reviewed", "peer_reviewed", "published", "preprint", "editorial", "user")
TIER_LABEL_ES = {
    "expert_peer_reviewed": "Revisado por pares · autor experto del área",
    "peer_reviewed": "Revisado por pares",
    "published": "Publicado (sin revisión por pares verificable)",
    "preprint": "Preprint (sin revisión por pares)",
    "editorial": "Nota editorial del proyecto",
    "user": "Aportado por un usuario",
}


@dataclass
class Author:
    name: str
    openalex_id: str | None = None
    orcid: str | None = None
    institution: str | None = None


@dataclass
class Candidate:
    source: str                      # conector
    title: str
    authors: list[Author]
    year: int | None
    abstract: str | None
    doi: str | None = None
    url: str | None = None
    venue: str | None = None
    venue_type: str | None = None    # journal, book, repository, conference…
    work_type: str | None = None     # article, book, book-chapter, preprint…
    language: str | None = None
    cited_by: int | None = None
    is_retracted: bool = False
    is_oa: bool | None = None
    license: str | None = None
    openalex_id: str | None = None
    topic: str | None = None
    tier: str = "published"
    raw_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConnectorReport:
    connector: str
    query: str
    ok: bool
    candidates: list[Candidate] = field(default_factory=list)
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"connector": self.connector, "query": self.query, "ok": self.ok, "error": self.error,
                "candidates": [c.as_dict() for c in self.candidates]}


def clean_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    d = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", doi.strip(), flags=re.I)
    return d.lower() or None


def strip_markup(text: str | None) -> str | None:
    if not text:
        return None
    t = re.sub(r"<[^>]+>", " ", text)
    t = re.sub(r"\s+", " ", t).strip()
    return t or None


class Connector:
    name = "base"

    def __init__(self, client: httpx.Client | None = None):
        self._client = client

    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = http_client(headers=self.auth_headers())
        return self._client

    def auth_headers(self) -> dict[str, str]:
        return {}

    def search(self, query: str, limit: int = 5) -> ConnectorReport:
        try:
            return ConnectorReport(self.name, query, True, self._search(query, limit))
        except httpx.HTTPStatusError as e:
            body = e.response.text[:200].replace("\n", " ")
            return ConnectorReport(self.name, query, False, error=f"HTTP {e.response.status_code}: {body}")
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as e:
            return ConnectorReport(self.name, query, False, error=f"{type(e).__name__}: {e}")

    def _search(self, query: str, limit: int) -> list[Candidate]:
        raise NotImplementedError
