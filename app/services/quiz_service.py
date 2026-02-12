"""Business logic for quiz answers and user progress."""

import logging

from app.models.quiz import AnswerResponse
from app.services.level_service import (
    get_animal_name_at,
    get_level_animal_count,
    get_level_ids,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory mock storage — TODO: Replace with Firestore
# ---------------------------------------------------------------------------
# user_id -> { level_id -> [bool, ...] }
_user_progress: dict[str, dict[int, list[bool]]] = {}
# user_id -> int
_user_coins: dict[str, int] = {}

# Coins awarded per correct answer equals the level's rarity number
COINS_PER_LEVEL: dict[int, int] = {i: i for i in range(1, 11)}


def _ensure_progress(user_id: str) -> dict[int, list[bool]]:
    """Initialise progress for a user if not already present."""
    if user_id not in _user_progress:
        _user_progress[user_id] = {
            lid: [False] * get_level_animal_count(lid)
            for lid in get_level_ids()
        }
        _user_coins.setdefault(user_id, 0)
    return _user_progress[user_id]


def submit_answer(user_id: str, level_id: int, animal_index: int, answer: str) -> AnswerResponse | None:
    """Check an answer and update progress / coins.

    Returns None if level_id or animal_index is invalid.
    """
    correct_name = get_animal_name_at(level_id, animal_index)
    if correct_name is None:
        return None

    progress = _ensure_progress(user_id)
    level_progress = progress.get(level_id)
    if level_progress is None or animal_index >= len(level_progress):
        return None

    is_correct = answer.strip().lower() == correct_name.lower()
    coins_awarded = 0

    if is_correct and not level_progress[animal_index]:
        level_progress[animal_index] = True
        coins_awarded = COINS_PER_LEVEL.get(level_id, 1)
        _user_coins[user_id] = _user_coins.get(user_id, 0) + coins_awarded

    total_coins = _user_coins.get(user_id, 0)

    return AnswerResponse(
        correct=is_correct,
        coins_awarded=coins_awarded,
        total_coins=total_coins,
        correct_answer=None if is_correct else correct_name,
    )


def get_user_progress(user_id: str) -> dict[str, list[bool]]:
    """Return progress per level as ``{level_id_str: [bool, ...]}``."""
    progress = _ensure_progress(user_id)
    return {str(lid): bools for lid, bools in progress.items()}


def get_user_coins(user_id: str) -> int:
    """Return total coins for a user."""
    _ensure_progress(user_id)
    return _user_coins.get(user_id, 0)


def get_user_level_guessed(user_id: str, level_id: int) -> list[bool]:
    """Return guessed list for a single level."""
    progress = _ensure_progress(user_id)
    return progress.get(level_id, [])


def count_completed_levels(user_id: str) -> int:
    """Return the number of levels where all animals are guessed."""
    progress = _ensure_progress(user_id)
    return sum(1 for bools in progress.values() if bools and all(bools))
