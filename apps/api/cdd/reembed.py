"""Recalcula los vectores de la biblioteca con el proveedor de embeddings activo.

Uso (desde apps/api), después de poner CDD_EMBEDDINGS_PROVIDER=gemini en .env:
  python -m cdd.reembed            # solo los fragmentos calculados con otro modelo
  python -m cdd.reembed --dry-run  # muestra cuántos y el coste aproximado, sin cambiar nada
"""
from __future__ import annotations

import argparse
import sys

from .config import get_settings
from .db import DatabaseUnavailable, check_connection, close_pool, service_tx
from .library.embeddings import GeminiEmbedder, get_embedder


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--batch", type=int, default=50)
    a = ap.parse_args()
    try:
        check_connection()
    except DatabaseUnavailable as e:
        print(f"ERROR: {e}")
        return 2
    emb = get_embedder()
    s = get_settings()
    try:
        with service_tx() as conn:
            rows = conn.execute("select id, locator, content from public.document_chunks where embedding_model <> %s order by id",
                                (emb.name,)).fetchall()
        chars = sum(len(r["locator"]) + len(r["content"]) for r in rows)
        usd = chars / 4 / 1e6 * s.gemini_embedding_usd_per_mtok if isinstance(emb, GeminiEmbedder) else 0
        print(f"Modelo activo: {emb.name} · fragmentos por recalcular: {len(rows)} · coste aproximado: {usd:.4f} USD")
        if a.dry_run or not rows:
            return 0
        done = 0
        for i in range(0, len(rows), a.batch):
            part = rows[i:i + a.batch]
            texts = [f"{r['locator']}. {r['content']}" for r in part]
            vecs = emb.embed_many(texts) if isinstance(emb, GeminiEmbedder) else [emb.embed(t) for t in texts]
            with service_tx() as conn:
                for r, v in zip(part, vecs, strict=True):
                    conn.execute("update public.document_chunks set embedding=%s, embedding_model=%s where id=%s", (v, emb.name, r["id"]))
            done += len(part)
            print(f"  {done}/{len(rows)}", flush=True)
        print("✓ Listo: la búsqueda semántica usa ahora", emb.name)
        return 0
    finally:
        close_pool()


if __name__ == "__main__":
    sys.exit(main())
