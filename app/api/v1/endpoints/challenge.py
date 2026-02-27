"""Daily challenge endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.dependencies import get_current_user_id, get_locale
from app.models.auth import ApiErrorResponse
from app.models.quiz import AnswerResponse, ChallengeAnswerRequest, ChallengeTodayResponse
from app.services.challenge_service import (
    get_challenge_leaderboard,
    get_today_challenge,
    submit_challenge_answer,
)

router = APIRouter(prefix="/challenge", tags=["Challenge"])
limiter = Limiter(key_func=get_remote_address)


@router.get(
    "/today",
    response_model=ChallengeTodayResponse,
    summary="Get today's daily challenge",
)
@limiter.limit(settings.RATE_LIMIT)
async def challenge_today(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    locale: str = Depends(get_locale),
) -> ChallengeTodayResponse:
    """Return today's deterministic challenge animals and completion state."""
    return get_today_challenge(user_id, locale=locale)


@router.post(
    "/answer",
    response_model=AnswerResponse,
    responses={400: {"model": ApiErrorResponse}},
    summary="Submit an answer for today's daily challenge",
)
@limiter.limit(settings.RATE_LIMIT)
async def challenge_answer(
    request: Request,
    body: ChallengeAnswerRequest,
    user_id: str = Depends(get_current_user_id),
    locale: str = Depends(get_locale),
) -> AnswerResponse:
    """Submit an answer for a challenge animal index."""
    result = submit_challenge_answer(
        user_id,
        body.animal_index,
        body.answer,
        locale=locale,
        ad_revealed=body.ad_revealed,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "invalid_request", "message": "Invalid animalIndex"}},
        )
    return result


@router.get(
    "/leaderboard",
    summary="Get daily challenge leaderboard",
)
@limiter.limit(settings.RATE_LIMIT)
async def challenge_leaderboard(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    date: str = Query("today", description="Challenge date (YYYY-MM-DD) or 'today'"),
) -> dict:
    """Return ranking for a challenge date."""
    return get_challenge_leaderboard(date)
