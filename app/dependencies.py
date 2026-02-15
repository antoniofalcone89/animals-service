"""Shared FastAPI dependencies."""

import logging

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.services.auth_service import verify_token

SUPPORTED_LOCALES = {"it", "en"}
DEFAULT_LOCALE = "it"

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer()


async def get_token_claims(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> dict:
    """Verify the Bearer token and return decoded claims.

    Returns a dict with ``uid``, ``email`` and ``name`` keys.
    Used by ``/auth/register`` which needs the full claims.
    """
    claims = verify_token(credentials.credentials)
    if claims is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return claims


async def get_current_user_id(
    claims: dict = Depends(get_token_claims),
) -> str:
    """Extract the user ID from verified token claims.

    Standard dependency for all protected endpoints.
    """
    return claims["uid"]


async def get_locale(accept_language: str | None = Header(None)) -> str:
    """Extract locale from Accept-Language header, defaulting to Italian."""
    if accept_language:
        lang = accept_language.strip().split(",")[0].split("-")[0].lower()
        if lang in SUPPORTED_LOCALES:
            return lang
    return DEFAULT_LOCALE
