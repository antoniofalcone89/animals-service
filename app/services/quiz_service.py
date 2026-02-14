"""Business logic for quiz answers and user progress."""

import logging

from app.db.user_store import get_store
from app.models.quiz import AnswerResponse
from app.services.level_service import get_animal_name_at, get_level_detail

logger = logging.getLogger(__name__)

# Flat 10 coins per correct first-time answer
COINS_PER_CORRECT = 10


def submit_answer(user_id: str, level_id: int, animal_index: int, answer: str) -> AnswerResponse | None:
    """Check an answer and update progress / coins.

    Returns None if level_id or animal_index is invalid.
    """
    correct_name = get_animal_name_at(level_id, animal_index)
    if correct_name is None:
        return None

    store = get_store()
    progress = store.ensure_progress(user_id)
    level_progress = progress.get(level_id)
    if level_progress is None or animal_index >= len(level_progress):
        return None

    is_correct = answer.strip().lower() == correct_name.lower()
    coins_awarded = 0
    total_coins = store.get_coins(user_id)

    if is_correct and not level_progress[animal_index]:
        coins_awarded, total_coins = store.submit_answer_update(
            user_id, level_id, animal_index, COINS_PER_CORRECT,
        )

    return AnswerResponse(
        correct=is_correct,
        coins_awarded=coins_awarded,
        total_coins=total_coins,
        correct_answer=None if is_correct else correct_name,
    )


def get_user_progress(user_id: str) -> dict[str, list[dict]]:
    """Return progress per level enriched with full animal objects."""
    progress = get_store().ensure_progress(user_id)
    result: dict[str, list[dict]] = {}
    for lid, bools in progress.items():
        detail = get_level_detail(lid, bools)
        if detail is not None:
            result[str(lid)] = [
                a.model_dump(by_alias=True) for a in detail.animals
            ]
    return result


def get_user_coins(user_id: str) -> int:
    """Return total coins for a user."""
    return get_store().get_coins(user_id)


def get_user_level_guessed(user_id: str, level_id: int) -> list[bool]:
    """Return guessed list for a single level."""
    progress = get_store().ensure_progress(user_id)
    return progress.get(level_id, [])


def count_completed_levels(user_id: str) -> int:
    """Return the number of levels where all animals are guessed."""
    return get_store().count_completed(user_id)
