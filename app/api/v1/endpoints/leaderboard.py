"""Leaderboard endpoints."""

import logging

from fastapi import APIRouter, Depends, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.dependencies import get_current_user_id
from app.models.quiz import LeaderboardEntry
from app.services import auth_service
from app.services.quiz_service import count_completed_levels, get_user_coins

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/leaderboard", tags=["Leaderboard"])
limiter = Limiter(key_func=get_remote_address)


@router.get(
    "",
    summary="Get global leaderboard (paginated)",
)
@limiter.limit(settings.RATE_LIMIT)
async def leaderboard(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(50, le=100, description="Max entries to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> dict:
    """Return paginated global leaderboard ranked by total coins.

    TODO: Replace with a Firestore query ordered by totalCoins once persistence is added.
    The current implementation reads from the in-memory user store.
    """
    # Build entries from all known users
    all_users = []
    for uid, user_data in auth_service.get_all_users().items():
        coins = get_user_coins(uid)
        completed = count_completed_levels(uid)
        all_users.append((uid, user_data.get("username", ""), coins, completed))

    # Sort by coins descending
    all_users.sort(key=lambda u: u[2], reverse=True)

    total = len(all_users)
    page = all_users[offset: offset + limit]

    entries = [
        LeaderboardEntry(
            rank=offset + i + 1,
            user_id=uid,
            username=username,
            total_coins=coins,
            levels_completed=completed,
        ).model_dump(by_alias=True)
        for i, (uid, username, coins, completed) in enumerate(page)
    ]
    return {"entries": entries, "total": total}
