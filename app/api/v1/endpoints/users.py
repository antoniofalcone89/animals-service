"""User progress and profile endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.dependencies import get_current_user_id, get_locale
from app.models.auth import ApiErrorResponse, UpdateProfileRequest, User
from app.services import auth_service
from app.services.quiz_service import get_user_coins, get_user_points, get_user_progress

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])
limiter = Limiter(key_func=get_remote_address)


@router.get(
    "/me/progress",
    summary="Get all level progress for current user",
)
@limiter.limit(settings.RATE_LIMIT)
async def user_progress(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    locale: str = Depends(get_locale),
) -> dict:
    """Return per-level guessed status for the current user."""
    levels = get_user_progress(user_id, locale=locale)
    return {"levels": levels}


@router.get(
    "/me/coins",
    summary="Get current coin total",
)
@limiter.limit(settings.RATE_LIMIT)
async def user_coins(
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Return the user's total coin count."""
    total = get_user_coins(user_id)
    return {"totalCoins": total}


@router.get(
    "/me/points",
    summary="Get current points total",
)
@limiter.limit(settings.RATE_LIMIT)
async def user_points(
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Return the user's total points count."""
    total = get_user_points(user_id)
    return {"totalPoints": total}


@router.patch(
    "/me/profile",
    response_model=User,
    responses={401: {"model": ApiErrorResponse}},
    summary="Update user profile (username)",
)
@limiter.limit(settings.RATE_LIMIT)
async def update_profile(
    request: Request,
    body: UpdateProfileRequest,
    user_id: str = Depends(get_current_user_id),
) -> User:
    """Update the current user's profile fields (currently only username).

    TODO: Persist to Firestore once Firebase is integrated.
    """
    updates = {}
    if body.username is not None:
        updates["username"] = body.username

    user_data = auth_service.update_user(user_id, **updates)
    if user_data is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return User(**user_data)
