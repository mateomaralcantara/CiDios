"""Formato de referencias: APA 7 y Chicago autor-fecha (versión simplificada y determinista)."""
from __future__ import annotations

import re

PARTICLES = {"de", "del", "la", "van", "von", "der", "den", "da", "di", "le", "ben", "bar", "al"}
INSTITUTION_HINTS = ("library", "institut", "university", "universidad", "museum", "authority", "biblioteca", "monasterio",
                     "society", "project", "equipo", "academy")


def _is_institution(name: str) -> bool:
    n = name.lower()
    return any(h in n for h in INSTITUTION_HINTS) or "(" in name


def split_name(name: str) -> tuple[str, str]:
    """Devuelve (apellidos, nombres). Respeta «Apellido, Nombre» y partículas (van, de…)."""
    name = re.sub(r"\s+", " ", name).strip()
    if "," in name:
        last, first = [x.strip() for x in name.split(",", 1)]
        return last, first
    parts = name.split(" ")
    if len(parts) == 1:
        return parts[0], ""
    i = len(parts) - 1
    while i > 1 and parts[i - 1].lower() in PARTICLES:
        i -= 1
    return " ".join(parts[i:]), " ".join(parts[:i])


def initials(first: str) -> str:
    out = []
    for p in re.split(r"[\s]+", first):
        if not p:
            continue
        if "-" in p:
            out.append("-".join(x[0] + "." for x in p.split("-") if x))
        elif p.endswith(".") and len(p) <= 3:
            out.append(p)
        else:
            out.append(p[0] + ".")
    return " ".join(out)


def apa_author(name: str) -> str:
    if _is_institution(name):
        return name
    last, first = split_name(name)
    return f"{last}, {initials(first)}".strip().rstrip(",")


def apa_authors(names: list[str]) -> str:
    names = [n for n in names if n]
    if not names:
        return ""
    a = [apa_author(n) for n in names]
    if len(a) == 1:
        return a[0]
    if len(a) <= 20:
        return ", ".join(a[:-1]) + ", & " + a[-1]
    return ", ".join(a[:19]) + ", … " + a[-1]


def apa(entry: dict) -> str:
    authors = apa_authors(entry.get("authors") or [])
    year = f"({entry['year']})" if entry.get("year") else "(s. f.)"
    title = (entry.get("title") or "").rstrip(".")
    parts = [f"{authors} {year}." if authors else f"{title}. {year}."]
    if authors:
        ed = f" ({entry['edition']})" if entry.get("edition") else ""
        parts.append(f"*{title}*{ed}." if entry.get("ref_type") in ("book", "edition") else f"{title}{ed}.")
    container = entry.get("container_title") or entry.get("venue")
    if container:
        parts.append(f"*{container}*.")
    if entry.get("publisher") and entry.get("publisher") != container:
        parts.append(f"{entry['publisher']}.")
    if entry.get("doi"):
        parts.append(f"https://doi.org/{entry['doi']}")
    elif entry.get("url"):
        parts.append(entry["url"])
    return " ".join(p for p in parts if p.strip(". "))


def chicago(entry: dict) -> str:
    names = entry.get("authors") or []
    if names:
        last, first = (names[0], "") if _is_institution(names[0]) else split_name(names[0])
        first_a = f"{last}, {first}".strip(", ")
        rest = [n for n in names[1:4]]
        auth = first_a + ("" if not rest else ", " + ", ".join(rest[:-1]) + (", and " if len(rest) > 1 else "and ") + rest[-1])
        if len(names) > 4:
            auth += " et al"
    else:
        auth = ""
    year = str(entry.get("year") or "n.d.")
    title = (entry.get("title") or "").rstrip(".")
    t = f"*{title}*." if entry.get("ref_type") in ("book", "edition") else f"“{title}.”"
    container = entry.get("container_title") or entry.get("venue")
    tail = " ".join(x for x in [f"*{container}*." if container else "",
                                f"{entry['publisher']}." if entry.get("publisher") and entry.get("publisher") != container else "",
                                f"https://doi.org/{entry['doi']}." if entry.get("doi") else (entry.get("url") or "")] if x)
    return " ".join(x for x in [f"{auth}. {year}." if auth else f"{year}.", t, tail] if x).replace("..", ".")
