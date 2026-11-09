"""OpenAlex (https://openalex.org): obras, resúmenes y perfiles de autores (índice h). Requiere clave gratuita."""
from __future__ import annotations

from typing import Any

from ..config import get_settings
from .base import Author, Candidate, Connector, clean_doi

BASE = "https://api.openalex.org"


def abstract_from_index(inv: dict[str, list[int]] | None) -> str | None:
    if not inv:
        return None
    pos: dict[int, str] = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos)) or None


def _tier(w: dict[str, Any]) -> str:
    st = ((w.get("primary_location") or {}).get("source") or {}).get("type")
    t = w.get("type")
    if t in ("preprint", "posted-content") or st == "repository":
        return "preprint"
    if st == "journal" or t in ("book", "book-chapter", "monograph"):
        return "peer_reviewed" if st == "journal" else "published"
    return "published"


def work_to_candidate(w: dict[str, Any]) -> Candidate:
    loc = w.get("primary_location") or {}
    src = loc.get("source") or {}
    authors = []
    for a in w.get("authorships", []):
        au = a.get("author") or {}
        inst = (a.get("institutions") or [{}])
        authors.append(Author(name=au.get("display_name") or "", openalex_id=au.get("id"), orcid=au.get("orcid"),
                              institution=(inst[0] or {}).get("display_name") if inst else None))
    return Candidate(
        source="openalex", title=w.get("display_name") or w.get("title") or "", authors=authors,
        year=w.get("publication_year"), abstract=abstract_from_index(w.get("abstract_inverted_index")),
        doi=clean_doi(w.get("doi")), url=loc.get("landing_page_url") or (w.get("open_access") or {}).get("oa_url"),
        venue=src.get("display_name"), venue_type=src.get("type"), work_type=w.get("type"), language=w.get("language"),
        cited_by=w.get("cited_by_count"), is_retracted=bool(w.get("is_retracted")),
        is_oa=(w.get("open_access") or {}).get("is_oa"), license=loc.get("license"), openalex_id=w.get("id"),
        topic=(w.get("primary_topic") or {}).get("display_name"), tier=_tier(w), raw_id=w.get("id"))


class OpenAlexConnector(Connector):
    name = "openalex"

    def auth_headers(self) -> dict[str, str]:
        key = get_settings().openalex_api_key
        return {"Authorization": f"Bearer {key}"} if key else {}

    def _params(self, **p: Any) -> dict[str, Any]:
        s = get_settings()
        if s.contact_email:
            p["mailto"] = s.contact_email
        return p

    def _search(self, query: str, limit: int) -> list[Candidate]:
        r = self.client().get(f"{BASE}/works", params=self._params(
            search=query, filter="has_abstract:true", **{"per-page": limit}))
        r.raise_for_status()
        return [work_to_candidate(w) for w in r.json()["results"]]

    def author(self, author_id: str) -> dict[str, Any]:
        aid = author_id.rsplit("/", 1)[-1]
        r = self.client().get(f"{BASE}/authors/{aid}", params=self._params())
        r.raise_for_status()
        a = r.json()
        stats = a.get("summary_stats") or {}
        inst = a.get("last_known_institutions") or [{}]
        return {"openalex_id": a.get("id"), "name": a.get("display_name"), "orcid": a.get("orcid"),
                "h_index": stats.get("h_index"), "i10_index": stats.get("i10_index"), "works_count": a.get("works_count"),
                "cited_by_count": a.get("cited_by_count"), "institution": (inst[0] or {}).get("display_name") if inst else None,
                "topics": [t.get("display_name") for t in (a.get("topics") or [])[:5]]}

    def works_by_author(self, author_id: str, query: str, limit: int) -> list[Candidate]:
        aid = author_id.rsplit("/", 1)[-1]
        r = self.client().get(f"{BASE}/works", params=self._params(
            search=query, filter=f"author.id:{aid},has_abstract:true,is_retracted:false,type:article|book|book-chapter|review",
            **{"per-page": limit}))
        r.raise_for_status()
        return [work_to_candidate(w) for w in r.json()["results"]]
