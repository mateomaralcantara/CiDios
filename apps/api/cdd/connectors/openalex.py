from __future__ import annotations

from .base import Candidate, Connector


class OpenAlexConnector(Connector):
    name = "openalex"
    base_url = "https://api.openalex.org"

    def _search(self, query: str, limit: int) -> list[Candidate]:
        r = self.client.get(f"{self.base_url}/works", params={"search": query, "per-page": limit})
        r.raise_for_status()
        out = []
        for w in r.json()["results"]:
            ids = {k: v for k, v in (w.get("ids") or {}).items() if isinstance(v, str)}
            oa = w.get("open_access") or {}
            loc = w.get("primary_location") or {}
            out.append(Candidate(
                source=self.name, title=w.get("display_name") or w.get("title") or "",
                authors=[a["author"]["display_name"] for a in w.get("authorships", []) if a.get("author")],
                year=w.get("publication_year"), identifiers=ids,
                venue=((loc.get("source") or {}).get("display_name")), open_access_url=oa.get("oa_url"),
                license=loc.get("license"), raw_id=w.get("id")))
        return out
