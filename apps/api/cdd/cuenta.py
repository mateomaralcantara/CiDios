"""Gestiona una cuenta de Supabase Auth desde tu PC, sin depender del correo.

Uso (desde apps/api):
  python -m cdd.cuenta tu@correo.com                 # muestra el estado de la cuenta
  python -m cdd.cuenta tu@correo.com --confirmar     # marca el correo como confirmado
  python -m cdd.cuenta tu@correo.com --contrasena    # pide una contraseña nueva (no se muestra) y la guarda
Útil cuando el correo gratuito de Supabase no llega (límite de envíos o solo envía al equipo del proyecto).
Usa la conexión del backend (CDD_DATABASE_URL); nunca se ejecuta desde el navegador.
"""
from __future__ import annotations

import argparse
import getpass
import sys

import psycopg

from .db import DatabaseUnavailable, check_connection, close_pool, service_tx


def _crypt_schema(conn) -> str | None:
    row = conn.execute("""select n.nspname from pg_proc p join pg_namespace n on n.oid = p.pronamespace
                          where p.proname = 'crypt' order by n.nspname = 'extensions' desc limit 1""").fetchone()
    return row["nspname"] if row else None


def status(conn, email: str) -> dict | None:
    return conn.execute("""select u.id, u.email, u.email_confirmed_at, u.encrypted_password is not null as has_password,
                                  coalesce(r.role::text, 'user') as role
                           from auth.users u left join public.user_roles r on r.user_id = u.id
                           where lower(u.email) = lower(%s)""", (email,)).fetchone()


def confirm(conn, email: str) -> None:
    conn.execute("update auth.users set email_confirmed_at = coalesce(email_confirmed_at, now()) where lower(email) = lower(%s)",
                 (email,))


def set_password(conn, email: str, password: str) -> None:
    schema = _crypt_schema(conn)
    if not schema:
        raise RuntimeError("Falta la extensión pgcrypto (en Supabase viene activada: Database → Extensions → pgcrypto)")
    conn.execute(f"""update auth.users set encrypted_password = {schema}.crypt(%s, {schema}.gen_salt('bf')),
                     email_confirmed_at = coalesce(email_confirmed_at, now()) where lower(email) = lower(%s)""",
                 (password, email))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("email")
    ap.add_argument("--confirmar", action="store_true", help="marca el correo como confirmado")
    ap.add_argument("--contrasena", "--contraseña", dest="contrasena", action="store_true",
                    help="establece una contraseña nueva (también confirma el correo)")
    a = ap.parse_args()
    try:
        check_connection()
    except DatabaseUnavailable as e:
        print(f"ERROR: {e}")
        return 2
    password = None
    if a.contrasena:
        password = getpass.getpass("Contraseña nueva (no se muestra): ")
        if len(password) < 8:
            print("ERROR: usa al menos 8 caracteres.")
            return 1
        if getpass.getpass("Repítela: ") != password:
            print("ERROR: las contraseñas no coinciden.")
            return 1
    try:
        with service_tx() as conn:
            if not status(conn, a.email):
                print(f"ERROR: no existe ninguna cuenta con {a.email}. Créala en la web (Entrar → Soy nuevo) "
                      "o en Supabase (Authentication → Users → Add user).")
                return 1
            if a.confirmar:
                confirm(conn, a.email)
            if password:
                set_password(conn, a.email, password)
            s = status(conn, a.email)
    except psycopg.errors.InsufficientPrivilege:
        print("ERROR: tu usuario de base de datos no puede modificar auth.users. Hazlo en Supabase: Authentication → Users → "
              "tu usuario → «⋯» → Confirm email / Send password recovery, o bórralo y créalo con Add user → Auto Confirm User.")
        return 1
    finally:
        close_pool()
    pendiente = f"NO → python -m cdd.cuenta {a.email} --confirmar"
    print(f"Cuenta {s['email']}")
    print(f"  Correo confirmado: {'sí' if s['email_confirmed_at'] else pendiente}")
    print(f"  Contraseña: {'definida' if s['has_password'] else 'sin contraseña'}" + (" (actualizada ✓)" if password else ""))
    print(f"  Rol: {s['role']}")
    if a.confirmar or password:
        print("✓ Listo. Entra en la web con tu correo y contraseña (pestaña «Ya tengo cuenta»).")
    return 0

if __name__ == "__main__":
    sys.exit(main())
