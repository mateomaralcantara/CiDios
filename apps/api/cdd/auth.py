"""Verificación de identidad (Supabase Auth) y dependencias de autorización."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status

from .config import Settings, get_settings
from .db import service_tx

_jwks_client: jwt.PyJWKClient | None = None


@dataclass(frozen=True)
class Principal:
    user_id: str | None
    role: str  # 'anon' | 'user' | 'editor' | 'owner'
    claims: dict[str, Any] | None

    @property
    def is_authenticated(self) -> bool:
        return self.user_id is not None

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"

    @property
    def is_staff(self) -> bool:
        return self.role in ("owner", "editor")


ANON = Principal(user_id=None, role="anon", claims=None)


def _dev_allowed(s: Settings) -> bool:
    return s.dev_auth and s.env in ("development", "test")


def issue_dev_token(user_id: str, email: str, ttl_s: int = 3600) -> str:
    s = get_settings()
    if not _dev_allowed(s):
        raise RuntimeError("Los tokens de desarrollo están deshabilitados en este entorno")
    now = int(time.time())
    return jwt.encode(
        {"sub": user_id, "email": email, "role": "authenticated", "aud": s.jwt_audience,
         "iat": now, "exp": now + ttl_s, "iss": "cdd-dev"},
        s.dev_jwt_secret, algorithm="HS256",
    )


def decode_token(token: str) -> dict[str, Any]:
    s = get_settings()
    errors: list[str] = []
    if s.supabase_jwks_url:
        global _jwks_client
        _jwks_client = _jwks_client or jwt.PyJWKClient(s.supabase_jwks_url)
        try:
            key = _jwks_client.get_signing_key_from_jwt(token)
            return jwt.decode(token, key.key, algorithms=["RS256", "ES256"], audience=s.jwt_audience)
        except jwt.PyJWTError as e:
            errors.append(f"jwks: {e}")
    if s.supabase_jwt_secret:
        try:
            return jwt.decode(token, s.supabase_jwt_secret, algorithms=["HS256"], audience=s.jwt_audience)
        except jwt.PyJWTError as e:
            errors.append(f"hs256: {e}")
    if _dev_allowed(s):
        try:
            claims = jwt.decode(token, s.dev_jwt_secret, algorithms=["HS256"], audience=s.jwt_audience)
            if claims.get("iss") == "cdd-dev":
                return claims
        except jwt.PyJWTError as e:
            errors.append(f"dev: {e}")
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido")


def lookup_role(user_id: str) -> str:
    with service_tx() as conn:
        row = conn.execute("select role::text as role from public.user_roles where user_id = %s", (user_id,)).fetchone()
    return row["role"] if row else "user"


def get_principal(request: Request) -> Principal:
    header = request.headers.get("authorization", "")
    token = header[7:] if header.lower().startswith("bearer ") else request.query_params.get("access_token")
    if not token:
        return ANON
    claims = decode_token(token)
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token sin sujeto")
    return Principal(user_id=sub, role=lookup_role(sub), claims=claims)


def require_user(p: Principal = Depends(get_principal)) -> Principal:
    if not p.is_authenticated:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Autenticación requerida")
    return p


def require_owner(p: Principal = Depends(require_user)) -> Principal:
    if not p.is_owner:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo el propietario puede realizar esta operación")
    return p


def require_staff(p: Principal = Depends(require_user)) -> Principal:
    if not p.is_staff:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Se requiere rol editor o propietario")
    return p
