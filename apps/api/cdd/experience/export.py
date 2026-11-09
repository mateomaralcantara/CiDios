"""Exportación del contenido y sus referencias."""
from __future__ import annotations

from typing import Any


def _ref(r: dict[str, Any] | None) -> str:
    if not r:
        return ""
    parts = [", ".join(r["authors"]), f"*{r['title']}*"]
    for k in ("container_title", "edition", "publisher"):
        if r.get(k):
            parts.append(r[k])
    if r.get("year"):
        parts.append(str(r["year"]))
    url = (r.get("identifiers") or {}).get("url")
    return ". ".join(parts) + (f". {url}" if url else "") + "."


def to_markdown(packet: dict[str, Any], spec: dict[str, Any]) -> str:
    out = [f"# {spec['title']}", "", f"> Pregunta: {packet['question']}", "",
           f"Paquete de conocimiento `{packet['sha256'][:16]}…` · generado {packet['generated_at']}", ""]
    claims = {c["id"]: c for c in packet["claims"]}
    order = [e["claim_id"] for e in spec.get("events", [])] or [c["id"] for c in packet["claims"]]
    order += [c["id"] for c in packet["claims"] if c["id"] not in order]
    refs: dict[str, str] = {}
    out.append("## Afirmaciones")
    for cid in order:
        c = claims[cid]
        date = f" — {c['date']['label']} ({c['date']['precision_label']})" if c.get("date") else ""
        out += ["", f"### {c.get('subject') or c['slug']}{date}", "", c["statement"], "",
                f"*Categoría epistémica:* {c['category_label']} · *Disciplina:* {c['discipline']}"]
        for note, label in (("consensus_note", "Consenso"), ("insufficient_evidence_note", "Límites de la evidencia"),
                            ("future_research_note", "Investigación futura")):
            if c.get(note):
                out.append(f"*{label}:* {c[note]}")
        out.append("")
        for e in c["evidence"]:
            r = e.get("reference")
            if r:
                refs[r["slug"]] = _ref(r)
            src = f"{e['document']['title']}, «{e['locator']}»"
            out.append(f"- **{e['stance']}** — “{e['fragment']}” ({src}{'; ' + r['slug'] if r else ''})")
        for p in c.get("perspectives", []):
            out.append(f"- *Perspectiva — {p['label']}* ({p['tradition']}; {p['held_by']}): {p['summary']}")
    if packet.get("uncertainties"):
        out += ["", "## Incertidumbres", ""] + [f"- {u}" for u in packet["uncertainties"]]
    if packet.get("limitations"):
        out += ["", "## Limitaciones", ""] + [f"- {u}" for u in packet["limitations"]]
    out += ["", "## Referencias", ""] + [f"- [{k}] {v}" for k, v in sorted(refs.items())]
    return "\n".join(out) + "\n"
