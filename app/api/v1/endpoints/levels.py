"""Level endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.dependencies import get_current_user_id, get_locale
from app.models.auth import ApiErrorResponse
from app.models.quiz import Level, LevelDetail
from app.services.level_service import get_all_levels, get_level_detail
from app.services.quiz_service import get_user_level_guessed

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/levels", tags=["Levels"])
limiter = Limiter(key_func=get_remote_address)


@router.get(
    "",
    summary="List all levels with animals",
)
@limiter.limit(settings.RATE_LIMIT)
async def list_levels(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    locale: str = Depends(get_locale),
) -> dict:
    """Return all levels with their animals."""
    levels = get_all_levels(locale=locale)
    return {"levels": [level.model_dump(by_alias=True) for level in levels]}


@router.get(
    "/{level_id}",
    response_model=LevelDetail,
    responses={404: {"model": ApiErrorResponse}},
    summary="Get level detail with per-animal guessed status",
)
@limiter.limit(settings.RATE_LIMIT)
async def level_detail(
    request: Request,
    level_id: int,
    user_id: str = Depends(get_current_user_id),
    locale: str = Depends(get_locale),
) -> LevelDetail:
    """Return level detail including per-animal guessed status for the current user."""
    guessed = get_user_level_guessed(user_id, level_id)
    detail = get_level_detail(level_id, guessed, locale=locale)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "level_not_found", "message": f"Level {level_id} not found"}},
        )
    return detail
