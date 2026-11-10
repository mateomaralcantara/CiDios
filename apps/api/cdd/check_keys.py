"""Comprueba TODAS las claves y URLs configuradas: python -m cdd.check_keys

Lee apps/api/.env y apps/web/.env.local y prueba cada credencial contra su servicio real:
  1. CDD_DATABASE_URL                    → conexión a la base (Supabase o local)
  2. CDD_SUPABASE_URL / JWKS / JWT secret → verificación de sesiones de Supabase Auth
  3. NEXT_PUBLIC_SUPABASE_URL + clave pública (web) → Supabase acepta la clave y es del mismo proyecto
  4. Que la web NO contenga claves secretas (service_role / sb_secret_)
  5. CDD_GEMINI_API_KEY + CDD_GEMINI_MODEL → llamada mínima real (fracciones de céntimo)
  6. CDD_OPENALEX_API_KEY                → petición autenticada a OpenAlex
  7. Crossref, Europe PMC y arXiv        → accesibles (no requieren clave)
  8. NEXT_PUBLIC_API_URL                 → la API responde (solo si está arrancada)

Nunca muestra una clave completa. Sale con código 1 si alguna comprobación falla.
Ejecútalo desde apps/api:  .\\.venv\\Scripts\\python -m cdd.check_keys
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .config import get_settings, mask_secret
from .db import DatabaseUnavailable, _redact, check_connection
from .net import http_client

WEB_ENV = Path.cwd().parent / "web" / ".env.local"


def read_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.split(" #", 1)[0].strip().strip('"').strip("'")
    return out


def jwt_role(token: str) -> str | None:
    """Rol declarado en una clave JWT clásica de Supabase (anon / service_role), sin verificar la firma."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload)).get("role")
    except (IndexError, ValueError):
        return None


class Report:
    def __init__(self) -> None:
        self.failed = self.warned = 0

    def section(self, title: str) -> None:
        print(f"\n{title}")

    def ok(self, msg: str) -> None:
        print(f"  ✓ {msg}")

    def warn(self, msg: str) -> None:
        self.warned += 1
        print(f"  ⚠ {msg}")

    def fail(self, msg: str, fix: str = "") -> None:
        self.failed += 1
        print(f"  ✗ {msg}" + (f"\n    → {fix}" if fix else ""))


def check_database(r: Report) -> None:
    s = get_settings()
    r.section("1. Base de datos (CDD_DATABASE_URL)")
    try:
        check_connection(s.database_url)
        r.ok(f"Conecta: {_redact(s.database_url)}")
    except DatabaseUnavailable as e:
        r.fail(str(e).split("\n")[0], "Configúrala con:  .\\.venv\\Scripts\\python -m cdd.set_database_url")


def check_supabase_auth(r: Report, client: httpx.Client) -> str | None:
    s = get_settings()
    r.section("2. Supabase Auth en la API (verificación de sesiones)")
    ref = None
    if s.supabase_url:
        ref = urlparse(s.supabase_url).hostname
        r.ok(f"CDD_SUPABASE_URL = {s.supabase_url}")
    if s.supabase_jwks_url:
        try:
            res = client.get(s.supabase_jwks_url)
            keys = res.json().get("keys", []) if res.status_code == 200 else []
            if keys:
                r.ok(f"CDD_SUPABASE_JWKS_URL responde con {len(keys)} clave(s) de firma")
            else:
                r.fail(f"CDD_SUPABASE_JWKS_URL no devuelve claves (HTTP {res.status_code})",
                       "Si tu proyecto usa el secreto clásico, usa CDD_SUPABASE_JWT_SECRET (Project Settings → JWT Keys → Legacy JWT secret)")
            if ref and urlparse(s.supabase_jwks_url).hostname != ref:
                r.fail("CDD_SUPABASE_JWKS_URL y CDD_SUPABASE_URL son de proyectos distintos")
        except httpx.HTTPError as e:
            r.fail(f"No se pudo leer el JWKS: {type(e).__name__}")
    elif s.supabase_jwt_secret:
        if len(s.supabase_jwt_secret) < 32:
            r.fail("CDD_SUPABASE_JWT_SECRET parece demasiado corto", "Cópialo completo de Project Settings → JWT Keys → Legacy JWT secret")
        else:
            r.ok(f"CDD_SUPABASE_JWT_SECRET presente ({mask_secret(s.supabase_jwt_secret)}); se valida al iniciar sesión")
    elif s.dev_auth and s.env in ("development", "test"):
        r.warn("Sin Supabase Auth: solo funcionan los accesos de desarrollo (CDD_DEV_AUTH=true)")
    else:
        r.fail("Falta CDD_SUPABASE_JWKS_URL (o CDD_SUPABASE_JWT_SECRET): nadie podrá iniciar sesión",
               "CDD_SUPABASE_JWKS_URL=https://<ref>.supabase.co/auth/v1/.well-known/jwks.json")
    return ref


def check_web(r: Report, client: httpx.Client, api_ref: str | None) -> dict[str, str]:
    r.section(f"3. Web ({WEB_ENV})")
    env = read_env(WEB_ENV)
    if not env:
        r.fail(f"No existe o está vacío {WEB_ENV}", "copy apps\\web\\.env.example apps\\web\\.env.local")
        return env
    url = env.get("NEXT_PUBLIC_SUPABASE_URL", "")
    key = env.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY") or env.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")
    if env.get("NEXT_PUBLIC_DEV_AUTH", "").lower() == "true" and url:
        r.warn("NEXT_PUBLIC_DEV_AUTH=true junto a Supabase: pon false para usar solo cuentas reales")
    if not url or not key:
        r.warn("Sin NEXT_PUBLIC_SUPABASE_URL o clave pública: la web funcionará solo en modo desarrollo")
    else:
        if api_ref and urlparse(url).hostname != api_ref:
            r.fail("La web y la API apuntan a proyectos de Supabase distintos",
                   f"NEXT_PUBLIC_SUPABASE_URL ({url}) debe coincidir con CDD_SUPABASE_URL")
        try:
            res = client.get(f"{url.rstrip('/')}/auth/v1/settings", headers={"apikey": key})
            if res.status_code == 200:
                email = (res.json().get("external") or {}).get("email")
                r.ok(f"Supabase acepta la clave pública ({mask_secret(key)})" + ("; registro por correo activo" if email else ""))
                if email is False:
                    r.warn("El registro por correo está desactivado en Supabase (Authentication → Sign In / Providers → Email)")
            else:
                r.fail(f"Supabase rechaza la clave pública (HTTP {res.status_code})",
                       "Copia la «Publishable key» (o la anon key) de Project Settings → API Keys")
        except httpx.HTTPError as e:
            r.fail(f"No se pudo contactar con {url}: {type(e).__name__}", "Revisa NEXT_PUBLIC_SUPABASE_URL")
    r.section("4. Seguridad de la web (ninguna clave secreta en NEXT_PUBLIC_*)")
    leaks = [k for k, v in env.items() if k.startswith("NEXT_PUBLIC_") and v and
             (v.startswith("sb_secret_") or jwt_role(v) == "service_role")]
    if leaks:
        r.fail(f"¡Clave SECRETA en {', '.join(leaks)}! Todo lo NEXT_PUBLIC_ llega al navegador",
               "Sustitúyela por la Publishable/anon key y rota la secreta en Supabase (Project Settings → API Keys)")
    else:
        r.ok("No hay claves secretas en la configuración de la web")
    return env


def check_gemini(r: Report) -> None:
    from .providers.gemini import GeminiClient, GeminiError
    s = get_settings()
    r.section("5. Gemini (CDD_GEMINI_API_KEY)")
    if not s.gemini_api_key:
        r.warn("Sin clave: los especialistas con LLM no se usarán (modo determinista)")
        return
    try:
        res = GeminiClient().generate_json("Responde solo con el JSON pedido.", 'Devuelve {"estado": "ok"}.',
                                           {"type": "OBJECT", "properties": {"estado": {"type": "STRING"}}, "required": ["estado"]},
                                           max_output_tokens=256, attempts=1)
        r.ok(f"Clave válida ({mask_secret(s.gemini_api_key)}) · modelo {res.model} · coste de la prueba {res.usd:.6f} USD")
    except GeminiError as e:
        r.fail(str(e)[:220], "Crea o copia la clave en https://aistudio.google.com/apikey y revisa CDD_GEMINI_MODEL")
        return
    if s.embeddings_provider == "gemini":
        try:
            v = GeminiClient().embed(["prueba de embeddings"], "RETRIEVAL_QUERY")
            r.ok(f"Embeddings con {s.gemini_embedding_model}: vector de {len(v[0])} dimensiones")
        except GeminiError as e:
            r.fail(f"Embeddings: {str(e)[:200]}", "Revisa CDD_GEMINI_EMBEDDING_MODEL o vuelve a CDD_EMBEDDINGS_PROVIDER=local")
    else:
        r.warn("Búsqueda semántica con el modelo local (léxico). Para usar Gemini: CDD_EMBEDDINGS_PROVIDER=gemini y python -m cdd.reembed")


def check_openalex(r: Report, client: httpx.Client) -> None:
    s = get_settings()
    r.section("6. OpenAlex (CDD_OPENALEX_API_KEY · dimensión 2: expertos)")
    if not s.openalex_api_key:
        r.warn("Sin clave: la búsqueda de expertos puede fallar (https://openalex.org/settings/api-key)")
        return
    if s.openalex_api_key != s.openalex_api_key.strip() or " " in s.openalex_api_key:
        r.fail("La clave tiene espacios", "Pégala sin espacios ni comillas")
        return
    try:
        res = client.get("https://api.openalex.org/works", params={"per-page": 1, "search": "test"},
                         headers={"Authorization": f"Bearer {s.openalex_api_key}"})
        if res.status_code == 200:
            r.ok(f"Clave válida ({mask_secret(s.openalex_api_key)})")
        elif res.status_code in (401, 403):
            r.fail(f"OpenAlex rechaza la clave (HTTP {res.status_code})",
                   "Pulsa «Copiar» en https://openalex.org/settings/api-key y pégala tal cual (no pulses «Girar»)")
        elif res.status_code == 429:
            r.warn("Clave aceptada pero sin cupo disponible hoy (HTTP 429)")
        else:
            r.fail(f"Respuesta inesperada de OpenAlex (HTTP {res.status_code})")
    except httpx.HTTPError as e:
        r.fail(f"No se pudo contactar con OpenAlex: {type(e).__name__}")


def check_open_sources(r: Report, client: httpx.Client) -> None:
    r.section("7. Repositorios sin clave")
    for name, url, params in [
        ("Crossref", "https://api.crossref.org/works", {"rows": 1, "query.bibliographic": "test"}),
        ("Europe PMC", "https://www.ebi.ac.uk/europepmc/webservices/rest/search", {"query": "test", "format": "json", "pageSize": 1}),
        ("arXiv", "https://export.arxiv.org/api/query", {"search_query": "all:test", "max_results": 1}),
    ]:
        try:
            res = client.get(url, params=params)
            (r.ok if res.status_code == 200 else r.warn)(f"{name}: HTTP {res.status_code}")
        except httpx.HTTPError as e:
            r.warn(f"{name}: sin respuesta ({type(e).__name__})")


def check_api(r: Report, client: httpx.Client, web_env: dict[str, str]) -> None:
    api = web_env.get("NEXT_PUBLIC_API_URL", "http://localhost:8000")
    r.section(f"8. API del proyecto ({api})")
    try:
        res = client.get(f"{api.rstrip('/')}/v1/health", timeout=4)
        (r.ok if res.status_code == 200 else r.fail)(f"/v1/health → HTTP {res.status_code}")
    except httpx.HTTPError:
        r.warn("La API no está arrancada (normal si no la has iniciado): .\\.venv\\Scripts\\uvicorn cdd.main:app --port 8000")


def main() -> int:
    s = get_settings()
    print(f"\nCIENCIA Y DIOS · comprobación de claves  (archivo: {Path.cwd() / '.env'})")
    if not (Path.cwd() / ".env").exists():
        print("  ✗ No hay .env en esta carpeta. Ejecuta el script desde apps\\api.")
        return 1
    r = Report()
    with http_client(timeout=15) as client:
        check_database(r)
        ref = check_supabase_auth(r, client)
        web = check_web(r, client, ref)
        check_gemini(r)
        check_openalex(r, client)
        if s.connectors_enabled:
            check_open_sources(r, client)
        check_api(r, client, web)
    print("\n" + ("Resultado: todas las claves funcionan" + (f" ({r.warned} aviso(s))" if r.warned else "") + "."
                  if not r.failed else f"Resultado: {r.failed} problema(s) (✗) y {r.warned} aviso(s). Sigue las indicaciones «→»."))
    return 1 if r.failed else 0


if __name__ == "__main__":
    sys.exit(main())
