"""Configuración centralizada. Los secretos solo se leen del entorno; nunca se exponen completos."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CDD_", env_file=".env", extra="ignore")

    env: Literal["development", "staging", "production", "test"] = "development"
    database_url: str = "postgresql://postgres@localhost:54329/cdd"

    # Autenticación Supabase: HS256 (secreto JWT del proyecto) o JWKS (claves asimétricas).
    supabase_url: str = ""
    supabase_jwt_secret: str = Field(default="", repr=False)
    supabase_jwks_url: str = ""
    jwt_audience: str = "authenticated"

    # Tokens de desarrollo: solo se aceptan si env == development|test y dev_auth está activo.
    dev_auth: bool = False
    dev_jwt_secret: str = Field(default="dev-only-insecure-secret-change-me-0123456789", repr=False)

    cors_origins: list[str] = ["http://localhost:3000"]

    # Proveedores de IA (opcionales). Sin clave, los agentes operan en modo determinista.
    anthropic_api_key: str = Field(default="", repr=False)
    anthropic_model: str = "claude-sonnet-5-5"

    # Conectores externos: desactivados por defecto; requieren red saliente permitida.
    connectors_enabled: list[str] = []
    connector_timeout_s: float = 10.0
    contact_agent: str = "CienciaYDios/0.1 (research platform)"

    default_run_budget_usd: float = 1.0
    worker_poll_interval_s: float = 0.5
    run_worker_in_api: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


def mask_secret(value: str) -> str:
    """Devuelve una pista no reversible de un secreto (nunca el valor completo)."""
    if not value:
        return ""
    if len(value) <= 8:
        return "•" * len(value)
    return f"{value[:4]}…{value[-2:]}"
