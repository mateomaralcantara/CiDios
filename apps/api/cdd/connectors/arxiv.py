"""arXiv (https://arxiv.org): preprints de física, matemáticas y computación. Sin revisión por pares."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from .base import Author, Candidate, Connector, clean_doi, strip_markup

BASE = "https://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def parse_feed(xml: str) -> list[Candidate]:
    root = ET.fromstring(xml)
    out = []
    for e in root.findall("a:entry", NS):
        published = e.findtext("a:published", default="", namespaces=NS)
        doi = e.findtext("arxiv:doi", default=None, namespaces=NS)
        jref = e.findtext("arxiv:journal_ref", default=None, namespaces=NS)
        out.append(Candidate(
            source="arxiv", title=strip_markup(e.findtext("a:title", default="", namespaces=NS)) or "",
            authors=[Author(name=a.findtext("a:name", default="", namespaces=NS)) for a in e.findall("a:author", NS)],
            year=int(published[:4]) if published[:4].isdigit() else None,
            abstract=strip_markup(e.findtext("a:summary", default="", namespaces=NS)), doi=clean_doi(doi),
            url=e.findtext("a:id", default=None, namespaces=NS), venue=jref or "arXiv",
            venue_type="journal" if jref else "repository", work_type="article" if jref else "preprint",
            tier="published" if jref else "preprint", raw_id=e.findtext("a:id", default=None, namespaces=NS)))
    return out


class ArxivConnector(Connector):
    name = "arxiv"

    def _search(self, query: str, limit: int) -> list[Candidate]:
        terms = [t for t in re.findall(r"[\w-]+", query) if len(t) > 2][:6]
        q = " AND ".join(f"all:{t}" for t in terms) or f"all:{query}"
        r = self.client().get(BASE, params={"search_query": q, "max_results": limit, "sortBy": "relevance"})
        r.raise_for_status()
        return parse_feed(r.text)
