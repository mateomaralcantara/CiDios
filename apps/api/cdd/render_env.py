"""Genera las variables de entorno para Render a partir de tu apps/api/.env (en tu PC, nunca se sube a git).

Uso (desde apps/api):
  python -m cdd.render_env --web-url https://tu-web.vercel.app
Crea apps/api/.env.render con valores de PRODUCCIÓN (sin tokens de desarrollo). En Render:
  servicio → Environment → «Add from .env» → pega el contenido → Save.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .check_keys import read_env

KEEP = ["CDD_DATABASE_URL", "CDD_SUPABASE_URL", "CDD_SUPABASE_JWKS_URL", "CDD_SUPABASE_JWT_SECRET", "CDD_GEMINI_API_KEY",
        "CDD_GEMINI_MODEL", "CDD_GEMINI_INPUT_USD_PER_MTOK", "CDD_GEMINI_OUTPUT_USD_PER_MTOK", "CDD_GEMINI_THINKING_BUDGET",
        "CDD_EMBEDDINGS_PROVIDER", "CDD_GEMINI_EMBEDDING_MODEL", "CDD_OPENALEX_API_KEY", "CDD_CONTACT_EMAIL",
        "CDD_CONNECTORS_ENABLED", "CDD_EXPERTS_MIN_H_INDEX"]
FORCED = {"CDD_ENV": "production", "CDD_DEV_AUTH": "false", "CDD_RUN_WORKER_IN_API": "true"}


def build(env: dict[str, str], web_urls: list[str]) -> tuple[list[str], list[str]]:
    lines, problems = [], []
    for k, v in FORCED.items():
        lines.append(f"{k}={v}")
    for k in KEEP:
        if env.get(k):
            lines.append(f"{k}={env[k]}")
    origins = sorted({u.rstrip("/") for u in web_urls if u})
    if origins:
        lines.append(f"CDD_CORS_ORIGINS={json.dumps(origins)}")
    else:
        problems.append("Falta --web-url (la URL de la web en Vercel): sin ella el navegador no podrá llamar a la API.")
    for k in ("CDD_DATABASE_URL", "CDD_SUPABASE_URL"):
        if not env.get(k):
            problems.append(f"Falta {k} en tu .env")
    if not (env.get("CDD_SUPABASE_JWKS_URL") or env.get("CDD_SUPABASE_JWT_SECRET")):
        problems.append("Falta CDD_SUPABASE_JWKS_URL (o CDD_SUPABASE_JWT_SECRET): en producción nadie podría iniciar sesión")
    if "localhost" in env.get("CDD_DATABASE_URL", "") or "127.0.0.1" in env.get("CDD_DATABASE_URL", ""):
        problems.append("CDD_DATABASE_URL apunta a tu PC (localhost): Render necesita la de Supabase")
    return lines, problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--web-url", action="append", default=[], help="URL pública de la web (puede repetirse)")
    a = ap.parse_args()
    src = Path.cwd() / ".env"
    if not src.exists():
        print("ERROR: ejecuta este comando desde apps\\api (no encuentro .env)")
        return 2
    lines, problems = build(read_env(src), a.web_url)
    out = Path.cwd() / ".env.render"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"✓ Generado {out} con {len(lines)} variables (no se sube a git).")
    print("  En Render: tu servicio → Environment → «Add from .env» → pega el contenido del archivo → Save.")
    for p in problems:
        print(f"  ⚠ {p}")
    return 1 if any("Falta CDD_" in p or "localhost" in p for p in problems) else 0


if __name__ == "__main__":
    sys.exit(main())
