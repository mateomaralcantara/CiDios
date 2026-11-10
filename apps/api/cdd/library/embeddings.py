"""Proveedores de embeddings.

``HashingEmbedder`` es un modelo base local, determinista y gratuito (hashing de rasgos léxicos:
unigramas sin acentos, raíces de 5 letras y bigramas). NO es un modelo semántico neuronal: captura
similitud léxica y morfológica. Se usa porque este despliegue no tiene acceso a un proveedor de
embeddings; el contrato ``Embedder`` permite sustituirlo sin cambiar el esquema (vector(384)).
"""
from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from typing import Protocol

DIM = 384

_STOP = set(
    ["el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al", "a", "en", "y", "o", "u", "que", "se", "su", "sus", "por", "para", "con", "sin", "es", "son", "fue", "fueron", "como", "más", "mas", "pero", "lo", "le", "les", "this", "the", "of", "and", "or", "to", "in", "is", "are", "was", "were", "on", "for", "with", "as", "by", "an"]
)


class Embedder(Protocol):
    name: str
    dim: int

    def embed(self, text: str) -> list[float]: ...


def _norm(text: str) -> list[str]:
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return [w for w in re.findall(r"[a-z0-9]+", t) if w not in _STOP and len(w) > 1]


class HashingEmbedder:
    name = "hashing-lexical-v1"
    dim = DIM

    def _feature(self, feat: str) -> tuple[int, float]:
        h = hashlib.blake2b(feat.encode(), digest_size=8).digest()
        idx = int.from_bytes(h[:4], "little") % self.dim
        sign = 1.0 if h[4] & 1 else -1.0
        return idx, sign

    def embed(self, text: str) -> list[float]:
        words = _norm(text)
        vec = [0.0] * self.dim
        feats: list[tuple[str, float]] = []
        for w in words:
            feats.append(("w:" + w, 1.0))
            if len(w) > 5:
                feats.append(("s:" + w[:5], 0.6))
        for a, b in zip(words, words[1:], strict=False):
            feats.append((f"b:{a}_{b}", 0.8))
        for f, wgt in feats:
            i, s = self._feature(f)
            vec[i] += s * wgt
        n = math.sqrt(sum(v * v for v in vec))
        return [v / n for v in vec] if n else vec


class GeminiEmbedder:
    """Embeddings semánticos de Gemini, reducidos a 384 dimensiones (mismo esquema vector(384))."""
    dim = DIM

    def __init__(self) -> None:
        from ..config import get_settings
        self.name = f"gemini:{get_settings().gemini_embedding_model}:{DIM}"

    def embed(self, text: str) -> list[float]:
        return self.embed_many([text], query=True)[0]

    def embed_many(self, texts: list[str], query: bool = False) -> list[list[float]]:
        from ..providers.gemini import GeminiClient
        return GeminiClient().embed(texts, "RETRIEVAL_QUERY" if query else "RETRIEVAL_DOCUMENT", DIM)


def get_embedder() -> Embedder:
    from ..config import get_settings
    s = get_settings()
    if s.embeddings_provider == "gemini" and s.gemini_api_key:
        return GeminiEmbedder()
    return HashingEmbedder()


def embed_documents(texts: list[str]) -> tuple[list[list[float]], str]:
    """Embeddings de fragmentos con el proveedor activo; si Gemini falla, respaldo léxico local (nunca bloquea la ingesta)."""
    emb = get_embedder()
    if isinstance(emb, GeminiEmbedder):
        try:
            return emb.embed_many(texts), emb.name
        except Exception:  # noqa: BLE001 — la red o la cuota no deben impedir incorporar documentos
            pass
    h = HashingEmbedder()
    return [h.embed(t) for t in texts], h.name


def embed_query(text: str) -> tuple[list[float], str]:
    emb = get_embedder()
    if isinstance(emb, GeminiEmbedder):
        try:
            return emb.embed(text), emb.name
        except Exception:  # noqa: BLE001
            pass
    h = HashingEmbedder()
    return h.embed(text), h.name
