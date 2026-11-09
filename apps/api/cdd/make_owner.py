"""Asigna el rol de propietario a un usuario ya registrado en Supabase Auth.

Uso: python -m cdd.make_owner tu@correo.com      (o --role editor / --role user)
Se ejecuta en el servidor con la conexión del backend; nunca desde el navegador.
"""
from __future__ import annotations

import argparse
import sys

from .db import DatabaseUnavailable, check_connection, close_pool, service_tx

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("email")
    ap.add_argument("--role", default="owner", choices=["owner", "editor", "user"])
    a = ap.parse_args()
    try:
        check_connection()
    except DatabaseUnavailable as e:
        sys.exit(f"ERROR: {e}")
    try:
        with service_tx() as conn:
            u = conn.execute("select id from auth.users where lower(email) = lower(%s)", (a.email,)).fetchone()
            if not u:
                sys.exit(f"ERROR: no existe ningún usuario con el correo {a.email}. Regístrate primero en la web "
                         "(Entrar → Crear cuenta) y confirma el correo.")
            conn.execute("insert into public.profiles (id, display_name) values (%s, %s) on conflict (id) do nothing",
                         (u["id"], a.email.split("@")[0]))
            conn.execute("""insert into public.user_roles (user_id, role) values (%s, %s)
                            on conflict (user_id) do update set role = excluded.role, granted_at = now()""", (u["id"], a.role))
        print(f"✓ {a.email} ahora tiene el rol «{a.role}». Cierra sesión y vuelve a entrar en la web.")
    finally:
        close_pool()
