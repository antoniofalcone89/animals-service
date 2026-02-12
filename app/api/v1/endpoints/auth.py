"""Authentication endpoints.

Authentication itself is handled client-side by Firebase (email/password,
Google Sign-In, etc.).  The Flutter app obtains a Firebase ID token and sends
it as a ``Bearer`` token with every request.

This module provides:
* ``POST /register`` — create an app profile after Firebase sign-up.
* ``GET  /me``       — retrieve the current user's profile.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.dependencies import get_current_user_id, get_token_claims
from app.models.auth import ApiErrorResponse, RegisterRequest, User
from app.services import auth_service
from app.services.quiz_service import get_user_coins

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])
limiter = Limiter(key_func=get_remote_address)


@router.post(
    "/register",
    response_model=User,
    status_code=201,
    responses={409: {"model": ApiErrorResponse}},
    summary="Register a new user profile",
)
@limiter.limit(settings.RATE_LIMIT)
async def register(
    request: Request,
    body: RegisterRequest,
    claims: dict = Depends(get_token_claims),
) -> User:
    """Create a user profile after authenticating with Firebase.

    The client must first register/sign-in via Firebase and then call this
    endpoint with the Firebase ID token as a Bearer token to create their
    app profile with a chosen username.
    """
    try:
        user_data = auth_service.create_user(
            uid=claims["uid"],
            email=claims["email"],
            username=body.username,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "user_already_exists", "message": "User profile already exists"}},
        )
    return User(**user_data)


@router.get(
    "/me",
    response_model=User,
    responses={
        401: {"model": ApiErrorResponse},
        404: {"model": ApiErrorResponse},
    },
    summary="Get current authenticated user",
)
@limiter.limit(settings.RATE_LIMIT)
async def get_current_user(
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> User:
    """Return the currently authenticated user's profile."""
    user_data = auth_service.get_user(user_id)
    if user_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "user_not_found",
                    "message": "User profile not found. Call POST /auth/register first.",
                }
            },
        )
    return User(
        id=user_data["id"],
        username=user_data["username"],
        email=user_data["email"],
        total_coins=get_user_coins(user_id),
        created_at=user_data["created_at"],
    )
