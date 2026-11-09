"""Crossref (https://api.crossref.org): metadatos editoriales, resolución de DOI y avisos de retractación."""
from __future__ import annotations

from typing import Any

from ..config import get_settings
from .base import Author, Candidate, Connector, clean_doi, strip_markup

BASE = "https://api.crossref.org"
PEER = {"journal-article", "proceedings-article", "book", "book-chapter", "monograph", "reference-entry"}


def item_to_candidate(it: dict[str, Any]) -> Candidate:
    parts = ((it.get("issued") or {}).get("date-parts") or [[None]])[0]
    t = it.get("type")
    retracted = any((u.get("type") or "").lower() in ("retraction", "removal") for u in it.get("updated-by") or [])
    return Candidate(
        source="crossref", title=(it.get("title") or [""])[0],
        authors=[Author(name=" ".join(x for x in (a.get("given"), a.get("family")) if x) or a.get("name", ""),
                        orcid=a.get("ORCID")) for a in it.get("author") or []],
        year=parts[0] if parts else None, abstract=strip_markup(it.get("abstract")), doi=clean_doi(it.get("DOI")),
        url=it.get("URL"), venue=(it.get("container-title") or [None])[0] or it.get("publisher"),
        venue_type="journal" if t == "journal-article" else t, work_type=t, language=it.get("language"),
        cited_by=it.get("is-referenced-by-count"), is_retracted=retracted,
        license=((it.get("license") or [{}])[0]).get("URL"),
        tier="peer_reviewed" if t == "journal-article" else ("preprint" if t == "posted-content" else "published"),
        raw_id=it.get("DOI"), extra={"publisher": it.get("publisher")})


class CrossrefConnector(Connector):
    name = "crossref"

    def _params(self, **p: Any) -> dict[str, Any]:
        s = get_settings()
        if s.contact_email:
            p["mailto"] = s.contact_email
        return p

    def _search(self, query: str, limit: int) -> list[Candidate]:
        r = self.client().get(f"{BASE}/works", params=self._params(**{"query.bibliographic": query, "rows": limit}))
        r.raise_for_status()
        return [item_to_candidate(it) for it in r.json()["message"]["items"]]

    def resolve(self, doi: str) -> Candidate | None:
        r = self.client().get(f"{BASE}/works/{clean_doi(doi)}", params=self._params())
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return item_to_candidate(r.json()["message"])
