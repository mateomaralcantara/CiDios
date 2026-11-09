from __future__ import annotations

from .base import Candidate, Connector


class CrossrefConnector(Connector):
    name = "crossref"
    base_url = "https://api.crossref.org"

    def _search(self, query: str, limit: int) -> list[Candidate]:
        r = self.client.get(f"{self.base_url}/works", params={"query.bibliographic": query, "rows": limit})
        r.raise_for_status()
        out = []
        for it in r.json()["message"]["items"]:
            parts = ((it.get("issued") or {}).get("date-parts") or [[None]])[0]
            lic = (it.get("license") or [{}])[0].get("URL")
            out.append(Candidate(
                source=self.name, title=(it.get("title") or [""])[0],
                authors=[" ".join(x for x in (a.get("given"), a.get("family")) if x) for a in it.get("author", [])],
                year=parts[0] if parts else None, identifiers={"doi": it["DOI"]} if it.get("DOI") else {},
                venue=(it.get("container-title") or [None])[0], license=lic, raw_id=it.get("DOI")))
        return out
