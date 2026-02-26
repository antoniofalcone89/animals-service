"""Leaderboard endpoints."""

import logging

from fastapi import APIRouter, Depends, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.dependencies import get_current_user_id
from app.models.quiz import LeaderboardEntry
from app.services import auth_service

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
    """Return paginated global leaderboard ranked by total points.

    Reads all data from a single ``get_all_users()`` call (which includes
    ``total_points`` and ``progress``) so that no extra per-user reads are
    needed.
    """
    all_users = []
    for uid, user_data in auth_service.get_all_users().items():
        points = user_data.get("total_points", 0)
        progress = user_data.get("progress", {})
        completed = sum(1 for bools in progress.values() if bools and all(bools))
        all_users.append((uid, user_data.get("username", ""), points, completed, user_data.get("photo_url")))

    # Sort by points descending
    all_users.sort(key=lambda u: u[2], reverse=True)

    total = len(all_users)
    page = all_users[offset: offset + limit]

    entries = [
        LeaderboardEntry(
            rank=offset + i + 1,
            user_id=uid,
            username=username,
            total_points=points,
            levels_completed=completed,
            photo_url=photo_url,
        ).model_dump(by_alias=True)
        for i, (uid, username, points, completed, photo_url) in enumerate(page)
    ]
    return {"entries": entries, "total": total}
