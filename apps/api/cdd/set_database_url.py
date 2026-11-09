"""Configura CDD_DATABASE_URL en apps/api/.env de forma segura.

Pide la contraseña sin mostrarla, la codifica (@ # / ? : …), prueba la conexión y solo si funciona
guarda la línea en .env (añadiendo sslmode=require para Supabase).

Uso (desde apps/api):
  python -m cdd.set_database_url
  python -m cdd.set_database_url "postgresql://postgres.<ref>:[YOUR-PASSWORD]@aws-0-<región>.pooler.supabase.com:5432/postgres"
"""
from __future__ import annotations

import getpass
import re
import sys
from pathlib import Path
from urllib.parse import quote

import psycopg

from .db import _redact

ENV_FILE = Path.cwd() / ".env"


def _current_url() -> str | None:
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("CDD_DATABASE_URL="):
                return line.split("=", 1)[1].strip()
    return None


def build_url(template: str, password: str) -> str:
    m = re.match(r"^(postgres(?:ql)?://)([^:/@]+):.*@([^@/]+)/([^?]*)(\?.*)?$", template.strip())
    if not m:
        raise ValueError("La cadena no tiene el formato postgresql://usuario:contraseña@host:puerto/base")
    scheme, user, host, db, query = m.groups()
    query = query or ""
    if "supabase" in host and "sslmode=" not in query:
        query += ("&" if query else "?") + "sslmode=require"
    return f"{scheme}{user}:{quote(password, safe='')}@{host}/{db or 'postgres'}{query}"


def save(url: str) -> None:
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    new, done = [], False
    for line in lines:
        if line.strip().startswith("CDD_DATABASE_URL="):
            if not done:
                new.append(f"CDD_DATABASE_URL={url}")
                done = True
            continue  # elimina duplicados
        new.append(line)
    if not done:
        new.insert(0, f"CDD_DATABASE_URL={url}")
    ENV_FILE.write_text("\n".join(new) + "\n", encoding="utf-8")


def main() -> int:
    template = sys.argv[1] if len(sys.argv) > 1 else _current_url()
    if not template:
        print("Pega la cadena de Supabase (Connect → Session pooler):")
        template = input("> ").strip()
    try:
        build_url(template, "x")
    except ValueError as e:
        print(f"ERROR: {e}")
        return 2
    print(f"Archivo: {ENV_FILE}")
    print(f"Conexión: {_redact(build_url(template, 'x'))}")
    password = getpass.getpass("Contraseña de la base de datos (no se ve al escribir): ")
    if not password:
        print("ERROR: contraseña vacía.")
        return 2
    url = build_url(template, password)
    print("Probando la conexión…")
    try:
        with psycopg.connect(url, connect_timeout=10) as conn:
            conn.execute("select 1")
    except psycopg.OperationalError as e:
        msg = str(e)
        if "password authentication failed" in msg:
            print("✗ La contraseña es incorrecta. No se ha cambiado nada en .env.\n"
                  "  Si no la recuerdas: Supabase → Project Settings → Database → Reset database password.")
        elif "tenant or user not found" in msg.lower():
            print("✗ El pooler no reconoce el proyecto: copia de nuevo la cadena desde Connect → Session pooler.")
        else:
            print(f"✗ No se pudo conectar: {msg.strip().splitlines()[-1] if msg.strip() else e}")
        return 1
    save(url)
    print(f"✓ Conexión correcta. Guardado en {ENV_FILE.name}: CDD_DATABASE_URL={_redact(url)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
