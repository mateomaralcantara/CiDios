"""Las pruebas usan un Postgres real (con pgvector) y el shim local de Supabase.

Variables: CDD_TEST_DATABASE_URL (por defecto postgresql://postgres:postgres@localhost:54329/cdd_test).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

TEST_DB = os.environ.get("CDD_TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:54329/cdd_test")
os.environ.update({"CDD_DATABASE_URL": TEST_DB, "CDD_ENV": "test", "CDD_DEV_AUTH": "true",
                   "CDD_RUN_WORKER_IN_API": "false", "CDD_CONNECTORS_ENABLED": "[]"})
ROOT = Path(__file__).resolve().parents[3]

FINAL_PROMPT = (
    "Investiga la historia de la transmisión de los textos bíblicos desde sus testimonios antiguos hasta las ediciones "
    "modernas. Muéstrame las evidencias arqueológicas y textuales, las posiciones académicas relevantes, las dataciones "
    "conocidas y las incertidumbres. Convierte la investigación en una línea de tiempo ilustrada y gamificada, con mapas, "
    "fuentes consultables, misiones pedagógicas, preguntas interactivas y narración opcional"
)


@pytest.fixture(scope="session", autouse=True)
def database():
    from cdd.dbreset import reset
    reset(TEST_DB)
    from cdd import seed
    from cdd.db import close_pool
    seed.run(dev_users=True)
    yield
    close_pool()


def principal(name: str):
    from cdd.auth import Principal
    from cdd.seed import DEV_USERS
    uid, email, role = DEV_USERS[name]
    return Principal(uid, role, {"sub": uid, "email": email, "role": "authenticated"})


@pytest.fixture
def owner():
    return principal("owner")


@pytest.fixture
def user():
    return principal("user")


@pytest.fixture
def user2():
    return principal("user2")


@pytest.fixture
def reset_costs():
    """Restaura costes de agentes y políticas tras pruebas que los modifican."""
    yield
    from cdd.db import service_tx
    with service_tx() as conn:
        conn.execute("update public.agent_definitions set unit_cost_usd=0, enabled=(status='operational'), max_cost_per_run_usd=1")
        conn.execute("update public.budget_policies set auto_approve_below_usd=0.50, limit_usd=1 where scope='investigation'")
