"""Configuración centralizada. Los secretos solo se leen del entorno; nunca se exponen completos."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _as_list(value: object) -> object:
    """Acepta listas JSON («["a","b"]») y también texto plano separado por comas («a, b»)."""
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("["):
            return json.loads(text)
        return [x.strip().strip('"').strip("'").rstrip("/") for x in text.split(",") if x.strip()]
    return value


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

    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    # --- LLM: Google Gemini (opcional). Sin clave, los agentes operan en modo determinista. ---
    gemini_api_key: str = Field(default="", repr=False)
    gemini_model: str = "gemini-2.5-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_timeout_s: float = 90.0
    # Precios en USD por millón de tokens: compruébalos en https://ai.google.dev/pricing y ajústalos.
    gemini_input_usd_per_mtok: float = 0.30
    gemini_output_usd_per_mtok: float = 2.50
    gemini_thinking_budget: int | None = None   # p. ej. 0 para desactivar el «razonamiento» en modelos flash
    # Embeddings: «local» (léxico, gratuito, sin red) o «gemini» (semántico real). Tras cambiarlo: python -m cdd.reembed
    embeddings_provider: Literal["local", "gemini"] = "local"
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_embedding_usd_per_mtok: float = 0.15
    llm_max_chunks: int = 24                    # fragmentos máximos que se envían al modelo por investigación
    llm_max_claims: int = 12                    # afirmaciones máximas que se le piden

    # Opcional (aún no lo usan los agentes)
    anthropic_api_key: str = Field(default="", repr=False)

    # --- Fuentes externas (dimensiones 1 y 2) ---
    connectors_enabled: Annotated[list[str], NoDecode] = ["openalex", "crossref", "europepmc", "arxiv"]
    connector_timeout_s: float = 20.0
    openalex_api_key: str = Field(default="", repr=False)   # gratuita: https://openalex.org (Authorization: Bearer)
    contact_email: str = ""                                  # tu correo para el «polite pool» de Crossref/OpenAlex (opcional)
    contact_agent: str = "CienciaYDios/0.2 (research platform)"
    published_max_works: int = 10                           # dimensión 1: obras publicadas a incorporar
    experts_max_authors: int = 5                            # dimensión 2: expertos a consultar
    experts_min_h_index: int = 15                           # umbral de experto (índice h en OpenAlex)
    experts_works_per_author: int = 3
    fulltext_max_works: int = 3                             # artículos de acceso abierto con texto completo por investigación

    # Protección contra abusos (0 = desactivado)
    rate_limit_per_minute: int = 300          # peticiones por IP y minuto a la API (sin contar OPTIONS de CORS)
    investigations_per_hour: int = 10         # investigaciones por usuario y hora (el propietario está exento)

    default_run_budget_usd: float = 1.0
    worker_poll_interval_s: float = 0.5
    run_worker_in_api: bool = True

    @model_validator(mode="after")
    def _default_jwks(self) -> Settings:
        # Supabase publica sus claves públicas en una ruta fija: con CDD_SUPABASE_URL basta
        if not self.supabase_jwks_url and self.supabase_url.startswith("https://"):
            self.supabase_jwks_url = self.supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"
        return self

    @field_validator("cors_origins", "connectors_enabled", mode="before")
    @classmethod
    def _split_lists(cls, value: object) -> object:
        return _as_list(value)


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
