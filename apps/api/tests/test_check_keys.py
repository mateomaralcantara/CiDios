"""El script de comprobación detecta claves válidas, inválidas y claves secretas expuestas en la web."""
from __future__ import annotations

import base64
import json

import httpx
import pytest

from cdd import check_keys, net
from cdd.config import get_settings


def fake_jwt(role: str) -> str:
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")  # noqa: E731
    return f"{enc({'alg': 'HS256'})}.{enc({'role': role})}.firma"


def handler(good: bool):
    def h(req: httpx.Request) -> httpx.Response:
        host = req.url.host
        if host == "ref.supabase.co" and req.url.path == "/auth/v1/settings":
            return httpx.Response(200 if req.headers.get("apikey") == "sb_publishable_ok" else 401, json={"external": {"email": True}})
        if host == "ref.supabase.co" and req.url.path.endswith("jwks.json"):
            return httpx.Response(200, json={"keys": [{"kid": "1"}]})
        if host == "generativelanguage.googleapis.com":
            if not good:
                return httpx.Response(400, json={"error": {"message": "API key not valid. Please pass a valid API key."}})
            return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '{"estado":"ok"}'}]}}],
                                             "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5}})
        if host == "api.openalex.org":
            return httpx.Response(200 if good else 401, json={"results": []})
        if host == "localhost":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(200, text="<feed/>", json=None) if host == "export.arxiv.org" else httpx.Response(200, json={})
    return h


@pytest.fixture
def setup(tmp_path, monkeypatch):
    (tmp_path / "api").mkdir()
    (tmp_path / "web").mkdir()
    (tmp_path / "api" / ".env").write_text("CDD_ENV=test\n")
    monkeypatch.chdir(tmp_path / "api")
    monkeypatch.setattr(check_keys, "WEB_ENV", tmp_path / "web" / ".env.local")
    s = get_settings()
    monkeypatch.setattr(s, "supabase_url", "https://ref.supabase.co")
    monkeypatch.setattr(s, "supabase_jwks_url", "https://ref.supabase.co/auth/v1/.well-known/jwks.json")
    monkeypatch.setattr(s, "gemini_api_key", "AIza-prueba")
    monkeypatch.setattr(s, "openalex_api_key", "oa-prueba")
    monkeypatch.setattr(s, "connectors_enabled", ["crossref"])
    return tmp_path / "web" / ".env.local"


def test_all_keys_ok(setup, monkeypatch, capsys):
    setup.write_text("NEXT_PUBLIC_API_URL=http://localhost:8000\nNEXT_PUBLIC_SUPABASE_URL=https://ref.supabase.co\n"
                     "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_ok\nNEXT_PUBLIC_DEV_AUTH=false\n")
    monkeypatch.setattr(net, "TRANSPORT", httpx.MockTransport(handler(True)))
    assert check_keys.main() == 0
    out = capsys.readouterr().out
    assert "Supabase acepta la clave pública" in out and "AIza-prueba" not in out and "oa-prueba" not in out


def test_bad_keys_and_secret_leak_are_reported(setup, monkeypatch, capsys):
    setup.write_text("NEXT_PUBLIC_SUPABASE_URL=https://ref.supabase.co\n"
                     f"NEXT_PUBLIC_SUPABASE_ANON_KEY={fake_jwt('service_role')}\n")
    monkeypatch.setattr(net, "TRANSPORT", httpx.MockTransport(handler(False)))
    assert check_keys.main() == 1
    out = capsys.readouterr().out
    assert "Supabase rechaza la clave pública" in out
    assert "¡Clave SECRETA en NEXT_PUBLIC_SUPABASE_ANON_KEY!" in out
    assert "Clave de Gemini no válida" in out and "OpenAlex rechaza la clave" in out
