"""Quiz answer endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.dependencies import get_current_user_id
from app.models.auth import ApiErrorResponse
from app.models.quiz import AnswerRequest, AnswerResponse
from app.services.quiz_service import submit_answer

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
) -> AnswerResponse:
    """Submit a quiz answer. Returns whether the answer is correct and coins awarded."""
    result = submit_answer(user_id, body.level_id, body.animal_index, body.answer)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "invalid_request", "message": "Invalid levelId or animalIndex"}},
        )
    return result
