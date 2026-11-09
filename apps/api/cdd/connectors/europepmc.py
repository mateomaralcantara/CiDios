"""Europe PMC (https://europepmc.org): literatura biomédica y de ciencias de la vida con resúmenes."""
from __future__ import annotations

from typing import Any

from .base import Author, Candidate, Connector, clean_doi, strip_markup

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"


def result_to_candidate(r: dict[str, Any]) -> Candidate:
    ji = r.get("journalInfo") or {}
    types = [t.lower() for t in ((r.get("pubTypeList") or {}).get("pubType") or [])]
    preprint = r.get("source") == "PPR" or "preprint" in types
    authors = []
    for a in ((r.get("authorList") or {}).get("author") or []):
        aid = a.get("authorId") or {}
        aff = ((a.get("authorAffiliationDetailsList") or {}).get("authorAffiliation") or [{}])
        authors.append(Author(name=a.get("fullName") or "", orcid=aid.get("value") if aid.get("type") == "ORCID" else None,
                              institution=(aff[0] or {}).get("affiliation") if aff else None))
    year = r.get("pubYear")
    return Candidate(
        source="europepmc", title=strip_markup(r.get("title")) or "", authors=authors,
        year=int(year) if str(year or "").isdigit() else None, abstract=strip_markup(r.get("abstractText")),
        doi=clean_doi(r.get("doi")), url=f"https://europepmc.org/article/{r.get('source')}/{r.get('id')}",
        venue=(ji.get("journal") or {}).get("title"), venue_type="repository" if preprint else "journal",
        work_type="preprint" if preprint else "article", language=r.get("language"), cited_by=r.get("citedByCount"),
        is_retracted="retraction of publication" in types or "retracted publication" in types,
        is_oa=r.get("isOpenAccess") == "Y", tier="preprint" if preprint else "peer_reviewed", raw_id=r.get("id"))


class EuropePMCConnector(Connector):
    name = "europepmc"

    def _search(self, query: str, limit: int) -> list[Candidate]:
        r = self.client().get(f"{BASE}/search", params={"query": f"({query}) AND HAS_ABSTRACT:y", "format": "json",
                                                         "pageSize": limit, "resultType": "core"})
        r.raise_for_status()
        return [result_to_candidate(x) for x in r.json()["resultList"]["result"]]
