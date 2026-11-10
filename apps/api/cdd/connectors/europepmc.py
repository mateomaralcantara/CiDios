"""Europe PMC (https://europepmc.org): literatura biomédica y de ciencias de la vida con resúmenes."""
from __future__ import annotations

import xml.etree.ElementTree as ET
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
        is_oa=r.get("isOpenAccess") == "Y", tier="preprint" if preprint else "peer_reviewed", raw_id=r.get("id"),
        license=(r.get("license") or None), extra={"pmcid": r.get("pmcid")} if r.get("pmcid") else {})


# Licencias que permiten reproducir el texto completo con atribución
FULLTEXT_LICENSES = {"cc by": "CC-BY-4.0", "cc-by": "CC-BY-4.0", "cc by-sa": "CC-BY-4.0", "cc-by-sa": "CC-BY-4.0",
                     "cc0": "PUBLIC-DOMAIN", "cc 0": "PUBLIC-DOMAIN"}
SKIP_SECTIONS = ("author contribution", "funding", "acknowledg", "conflict", "competing interest", "ethics", "data availability",
                 "supplementary", "abbreviation", "references", "declaration", "consent", "orcid", "peer review")
MAX_FULLTEXT_CHARS = 60_000


def fulltext_license_code(license_: str | None) -> str | None:
    return FULLTEXT_LICENSES.get((license_ or "").strip().lower())


def _text(el: ET.Element) -> str:
    return " ".join("".join(el.itertext()).split())


def parse_fulltext(xml: str) -> str | None:
    """Convierte el JATS de Europe PMC en texto con secciones «## Título» (para citar por sección)."""
    root = ET.fromstring(xml)
    body = root.find(".//body")
    if body is None:
        return None
    out: list[str] = []

    def walk(sec: ET.Element, prefix: str) -> None:
        title = _text(sec.find("title")) if sec.find("title") is not None else ""
        name = f"{prefix} — {title}" if prefix and title else (title or prefix)
        if any(s in name.lower() for s in SKIP_SECTIONS):
            return
        paras = [_text(p) for p in sec.findall("p") if _text(p)]
        if paras:
            out.append(f"## {name or 'Texto'}\n\n" + "\n\n".join(paras))
        for sub in sec.findall("sec"):
            walk(sub, name)

    for sec in body.findall("sec"):
        walk(sec, "")
    loose = [_text(p) for p in body.findall("p") if _text(p)]
    if loose:
        out.insert(0, "## Texto\n\n" + "\n\n".join(loose))
    text = "\n\n".join(out)
    return text[:MAX_FULLTEXT_CHARS] if text else None


class EuropePMCConnector(Connector):
    name = "europepmc"

    def full_text(self, pmcid: str) -> str | None:
        r = self.client().get(f"{BASE}/{pmcid}/fullTextXML")
        if r.status_code != 200:
            return None
        return parse_fulltext(r.text)

    def _search(self, query: str, limit: int) -> list[Candidate]:
        r = self.client().get(f"{BASE}/search", params={"query": f"({query}) AND HAS_ABSTRACT:y", "format": "json",
                                                         "pageSize": limit, "resultType": "core"})
        r.raise_for_status()
        return [result_to_candidate(x) for x in r.json()["resultList"]["result"]]
