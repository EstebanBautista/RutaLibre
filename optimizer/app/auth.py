"""Verifies the JWT issued by the Django backend.

Both services share one signing key (HS256). The optimizer never talks to
the database: a valid signature and an unexpired access token are enough.
"""

from __future__ import annotations

import os

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# Same development-only key the Django backend uses when nothing is configured,
# so both services work together locally with zero setup. Never used on Vercel.
_DEV_KEY = "dev-only-insecure-key-do-not-use-in-production-0123456789abcdef"


def _signing_key() -> str:
    configured = os.environ.get("JWT_SIGNING_KEY", "")
    if configured:
        return configured
    return "" if os.environ.get("VERCEL") == "1" else _DEV_KEY


_bearer = HTTPBearer(auto_error=False, description="Token de acceso emitido por el backend de RutaLibre")


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    """FastAPI dependency: returns the token claims or raises 401."""
    if credentials is None:
        raise _unauthorized("Falta el token de acceso")

    signing_key = _signing_key()
    if not signing_key:
        # Refuse everything rather than accept tokens signed with an empty key.
        raise _unauthorized("El servicio no tiene clave de verificación configurada")

    try:
        claims = jwt.decode(
            credentials.credentials,
            signing_key,
            algorithms=["HS256"],  # pinned: never trust the algorithm named in the token
            options={"require": ["exp"]},
        )
    except jwt.PyJWTError:
        raise _unauthorized("Token inválido o vencido") from None

    # simplejwt issues "access" and "refresh" tokens; only access tokens may call APIs.
    if claims.get("token_type") != "access":
        raise _unauthorized("Se requiere un token de acceso")
    return claims
