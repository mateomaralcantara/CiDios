"""Conectores a repositorios bibliográficos autorizados.

Los conectores solo DESCUBREN referencias candidatas (metadatos). Nunca se usan como evidencia de una
afirmación hasta que el documento correspondiente se incorpora legalmente a la biblioteca, se fragmenta
y una cita literal se verifica contra él.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from ..config import get_settings


@dataclass
class Candidate:
    source: str
    title: str
    authors: list[str]
    year: int | None
    identifiers: dict[str, str]
    venue: str | None = None
    open_access_url: str | None = None
    license: str | None = None
    raw_id: str | None = None


@dataclass
class ConnectorReport:
    connector: str
    query: str
    ok: bool
    candidates: list[Candidate] = field(default_factory=list)
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"connector": self.connector, "query": self.query, "ok": self.ok, "error": self.error,
                "candidates": [c.__dict__ for c in self.candidates]}


class Connector:
    name = "base"

    def __init__(self, client: httpx.Client | None = None):
        s = get_settings()
        self.client = client or httpx.Client(timeout=s.connector_timeout_s, headers={"User-Agent": s.contact_agent})

    def search(self, query: str, limit: int = 5) -> ConnectorReport:
        try:
            return ConnectorReport(self.name, query, True, self._search(query, limit))
        except (httpx.HTTPError, ValueError, KeyError) as e:
            return ConnectorReport(self.name, query, False, error=f"{type(e).__name__}: {e}")

    def _search(self, query: str, limit: int) -> list[Candidate]:
        raise NotImplementedError
