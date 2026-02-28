"""Business logic for daily challenge endpoints."""

import random
from datetime import date, datetime, timezone

from app.db.user_store import get_store
from app.models.quiz import (
    AnswerResponse,
    ChallengeLeaderboardEntry,
    ChallengeTodayResponse,
)
from app.services import auth_service
from app.services.achievement_service import evaluate_daily_challenge_achievement
from app.services.quiz_service import _is_fuzzy_match
from app.services.level_service import get_flat_animals

CHALLENGE_SIZE = 10


def _challenge_date_iso(challenge_date: date | None = None) -> str:
    target = challenge_date or datetime.now(timezone.utc).date()
    return target.isoformat()


def _daily_animals(challenge_date: str, locale: str) -> list[dict]:
    flat = get_flat_animals(locale=locale)
    if len(flat) <= CHALLENGE_SIZE:
        return flat
    rng = random.Random(challenge_date)
    indexes = sorted(rng.sample(range(len(flat)), CHALLENGE_SIZE))
    return [flat[i] for i in indexes]


def get_today_challenge(user_id: str, locale: str = "it") -> ChallengeTodayResponse:
    challenge_date = _challenge_date_iso()
    animals = _daily_animals(challenge_date, locale)
    state = get_store().get_daily_challenge(user_id, challenge_date, len(animals))
    completed = bool(state.get("completed_at")) or all(state.get("answered", []))
    score = int(state.get("score", 0) or 0) if completed else None
    return ChallengeTodayResponse(
        date=challenge_date,
        animals=[entry["animal"] for entry in animals],
        completed=completed,
        score=score,
    )


def submit_challenge_answer(
    user_id: str,
    animal_index: int,
    answer: str,
    locale: str = "it",
    ad_revealed: bool = False,
) -> AnswerResponse | None:
    challenge_date = _challenge_date_iso()
    animals = _daily_animals(challenge_date, locale)
    if animal_index < 0 or animal_index >= len(animals):
        return None

    correct_name = animals[animal_index]["animal"].name
    is_correct = _is_fuzzy_match(answer, correct_name)

    points_awarded = 3 if ad_revealed else 20
    points_now = 0
    completed = False
    new_achievements: list[str] = []
    if is_correct:
        points_now, _, completed, _ = get_store().submit_daily_challenge_answer(
            user_id,
            challenge_date,
            animal_index,
            points_awarded,
            len(animals),
        )
        if completed and points_now > 0:
            new_achievements = evaluate_daily_challenge_achievement(user_id)

    user_data = get_store().get_user(user_id) or {}
    total_coins = get_store().get_coins(user_id)

    return AnswerResponse(
        correct=is_correct,
        coins_awarded=0,
        total_coins=total_coins,
        points_awarded=points_now,
        correct_answer=correct_name,
        current_streak=int(user_data.get("current_streak", 0) or 0),
        last_activity_date=user_data.get("last_activity_date"),
        streak_bonus_coins=0,
        new_achievements=new_achievements,
    )


def get_challenge_leaderboard(challenge_date: str | None = None) -> dict:
    date_iso = _challenge_date_iso() if not challenge_date or challenge_date == "today" else challenge_date
    rows = get_store().get_daily_challenge_leaderboard(date_iso)
    users = auth_service.get_all_users()

    rows.sort(
        key=lambda row: (
            -int(row.get("score", 0) or 0),
            row.get("completed_at") or datetime.max.replace(tzinfo=timezone.utc),
        )
    )

    entries = []
    for idx, row in enumerate(rows, start=1):
        uid = row["user_id"]
        user_data = users.get(uid, {})
        completed_at = row.get("completed_at")
        entries.append(
            ChallengeLeaderboardEntry(
                rank=idx,
                user_id=uid,
                username=user_data.get("username", ""),
                score=int(row.get("score", 0) or 0),
                completed_at=completed_at.isoformat() if completed_at else None,
                photo_url=user_data.get("photo_url"),
            ).model_dump(by_alias=True)
        )

    return {"date": date_iso, "entries": entries, "total": len(entries)}
