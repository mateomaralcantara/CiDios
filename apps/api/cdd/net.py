"""Fábrica de clientes HTTP. Las pruebas sustituyen TRANSPORT por un httpx.MockTransport."""
from __future__ import annotations

import httpx

from .config import get_settings

TRANSPORT: httpx.BaseTransport | None = None


def http_client(timeout: float | None = None, headers: dict[str, str] | None = None) -> httpx.Client:
    s = get_settings()
    h = {"User-Agent": s.contact_agent + (f" mailto:{s.contact_email}" if s.contact_email else "")}
    h.update(headers or {})
    return httpx.Client(timeout=timeout or s.connector_timeout_s, headers=h, transport=TRANSPORT, follow_redirects=True)
