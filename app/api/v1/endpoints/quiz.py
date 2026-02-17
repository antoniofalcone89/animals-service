"""Quiz answer endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.dependencies import get_current_user_id, get_locale
from app.models.auth import ApiErrorResponse
from app.models.quiz import AnswerRequest, AnswerResponse, BuyHintRequest, BuyHintResponse
from app.services.quiz_service import buy_hint, submit_answer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quiz", tags=["Quiz"])
limiter = Limiter(key_func=get_remote_address)


@router.post(
    "/answer",
    response_model=AnswerResponse,
    response_model_exclude_none=True,
    responses={400: {"model": ApiErrorResponse}},
    summary="Submit an answer for an animal in a level",
)
@limiter.limit(settings.RATE_LIMIT)
async def post_answer(
    request: Request,
    body: AnswerRequest,
    user_id: str = Depends(get_current_user_id),
    locale: str = Depends(get_locale),
) -> AnswerResponse:
    """Submit a quiz answer. Returns whether the answer is correct and coins awarded."""
    result = submit_answer(user_id, body.level_id, body.animal_index, body.answer, locale=locale)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "invalid_request", "message": "Invalid levelId or animalIndex"}},
        )
    return result


@router.post(
    "/buy-hint",
    response_model=BuyHintResponse,
    responses={400: {"model": ApiErrorResponse}},
    summary="Buy a hint for an animal in a level",
)
@limiter.limit(settings.RATE_LIMIT)
async def post_buy_hint(
    request: Request,
    body: BuyHintRequest,
    user_id: str = Depends(get_current_user_id),
) -> BuyHintResponse:
    """Buy the next hint for an animal. Cost escalates with each hint purchased."""
    try:
        return buy_hint(user_id, body.level_id, body.animal_index)
    except ValueError as exc:
        code = str(exc)
        messages = {
            "insufficient_coins": "Not enough coins",
            "max_hints_reached": "All hints already revealed",
            "invalid level/index": "Invalid levelId or animalIndex",
        }
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": code, "message": messages.get(code, code)}},
        )
