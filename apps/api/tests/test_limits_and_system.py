"""Límites anti-abuso y panel de monitorización."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cdd import main
from cdd.config import get_settings
from cdd.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def tok(client, who):
    return {"Authorization": f"Bearer {client.post('/v1/auth/dev-token', json={'user': who}).json()['access_token']}"}


def test_rate_limit_per_ip(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_per_minute", 3)
    main._hits.clear()
    codes = [client.get("/v1/topics").status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    assert client.get("/v1/health").status_code == 200       # el health check no se limita
    main._hits.clear()


def test_investigations_per_hour_limit_and_owner_exemption(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "investigations_per_hour", 1)
    h = tok(client, "user2")
    body = {"prompt": "Investiga el Códice Sinaítico y su datación", "force_new": True}
    first = client.post("/v1/investigations", json=body, headers=h)
    assert first.status_code in (201, 429)       # puede haber otra de user2 en la última hora
    second = client.post("/v1/investigations", json=body, headers=h)
    assert second.status_code == 429 and "límite" in second.json()["detail"]
    o = tok(client, "owner")
    assert client.post("/v1/investigations", json=body, headers=o).status_code == 201
    assert client.post("/v1/investigations", json=body, headers=o).status_code == 201


def test_system_panel(client):
    assert client.get("/v1/admin/system", headers=tok(client, "user")).status_code == 403
    d = client.get("/v1/admin/system", headers=tok(client, "owner")).json()
    assert {"worker", "runs", "spend_24h", "recent_errors", "embeddings", "db_latency_ms", "limits"} <= set(d)
    assert d["embeddings"]["active"] == "hashing-lexical-v1" and d["db_latency_ms"] >= 0
    assert client.get("/v1/health").json()["worker"] == "disabled"   # en pruebas el worker no corre dentro de la API
