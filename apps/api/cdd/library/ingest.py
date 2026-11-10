"""Pipeline documental.

descubrimiento → permiso de acceso → recuperación → extracción → normalización → deduplicación →
clasificación → fragmentación → indexación → (vinculación de afirmaciones → verificación → publicación,
en evidence/).
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from psycopg import Connection

from ..security.injection import scan
from .embeddings import embed_documents


class LicenseBlocked(Exception):
    pass


class DuplicateDocument(Exception):
    def __init__(self, existing_id: str):
        super().__init__(f"Documento duplicado: {existing_id}")
        self.existing_id = existing_id


@dataclass
class DocumentInput:
    title: str
    body: str
    doc_kind: str
    license_code: str
    authors: list[str] = field(default_factory=list)
    institution: str | None = None
    published_date: str | None = None
    language: str = "es"
    edition: str | None = None
    identifier: str | None = None
    rights_statement: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)
    slug: str | None = None
    visibility: str = "private"
    review_status: str = "draft"
    cites: list[str] = field(default_factory=list)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode()).hexdigest()


def chunk_text(body: str, max_chars: int = 900) -> list[tuple[str, str]]:
    """Fragmenta por secciones ``## Título`` (que pasan a ser el localizador) y párrafos."""
    chunks: list[tuple[str, str]] = []
    locator = "§0"
    buf: list[str] = []

    def flush() -> None:
        if buf:
            chunks.append((locator, "\n\n".join(buf).strip()))
            buf.clear()

    for para in body.split("\n\n"):
        p = para.strip()
        if not p:
            continue
        m = re.match(r"^#{1,3}\s+(.*)$", p)
        if m:
            flush()
            locator = m.group(1).strip()
            continue
        if sum(len(b) for b in buf) + len(p) > max_chars:
            flush()
        buf.append(p)
    flush()
    return chunks


def check_license(conn: Connection, code: str) -> dict[str, Any]:
    lic = conn.execute("select * from public.licenses where code = %s", (code,)).fetchone()
    if lic is None:
        raise LicenseBlocked(f"Licencia desconocida: {code}")
    if not lic["allows_excerpt"]:
        raise LicenseBlocked(f"La licencia {code} no permite almacenar extractos")
    return lic


def ingest_document(conn: Connection, doc: DocumentInput, owner_id: str | None) -> dict[str, Any]:
    check_license(conn, doc.license_code)
    body = normalize_text(doc.body)
    digest = content_hash(body)
    existing = conn.execute("select id from public.documents where content_sha256 = %s", (digest,)).fetchone()
    if existing:
        raise DuplicateDocument(str(existing["id"]))
    row = conn.execute(
        """insert into public.documents (slug, title, doc_kind, authors, institution, published_date, language,
             edition, identifier, license_code, rights_statement, provenance, consulted_at, content_sha256, body,
             owner_id, visibility, review_status, cites)
           values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now(),%s,%s,%s,%s,%s,%s::uuid[]) returning id""",
        (doc.slug, doc.title, doc.doc_kind, doc.authors, doc.institution, doc.published_date, doc.language,
         doc.edition, doc.identifier, doc.license_code, doc.rights_statement, json.dumps(doc.provenance), digest,
         body, owner_id, doc.visibility, doc.review_status, doc.cites),
    ).fetchone()
    doc_id = row["id"]
    chunks = chunk_text(body)
    vectors, model = embed_documents([f"{loc}. {content}" for loc, content in chunks])
    flagged = 0
    for i, ((locator, content), vec) in enumerate(zip(chunks, vectors, strict=True)):
        signals = scan(content)
        flagged += bool(signals)
        conn.execute(
            """insert into public.document_chunks (document_id, ordinal, locator, content, embedding, embedding_model,
                 injection_risk, injection_signals) values (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (doc_id, i, locator, content, vec, model, bool(signals), signals),
        )
    n = conn.execute("select count(*) as n from public.document_chunks where document_id=%s", (doc_id,)).fetchone()["n"]
    return {"id": str(doc_id), "chunks": n, "flagged_chunks": flagged, "sha256": digest}
