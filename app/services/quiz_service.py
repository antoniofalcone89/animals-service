"""Business logic for quiz answers and user progress."""

import logging

from app.config import settings
from app.db.user_store import get_store
from app.models.quiz import AnswerResponse, BuyHintResponse, RevealLetterResponse
from app.services.level_service import get_animal_name_at, get_level_detail

logger = logging.getLogger(__name__)

# Flat 10 coins per correct first-time answer
COINS_PER_CORRECT = 10


def _calculate_points(ad_revealed: bool, hints_used: int, letters_used: int) -> int:
    """Calculate points for a correct answer based on assists used."""
    if ad_revealed:
        return 3
    total_assists = hints_used + letters_used
    if total_assists == 0:
        return 20
    if total_assists == 1:
        return 15
    if total_assists == 2:
        return 10
    return 5


def _levenshtein(a: str, b: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(a) < len(b):
        return _levenshtein(b, a)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            cost = 0 if ca == cb else 1
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + cost))
        prev = curr
    return prev[-1]


def _is_fuzzy_match(guess: str, correct: str) -> bool:
    """Check if guess matches correct answer within Levenshtein threshold."""
    g = guess.strip().lower()
    c = correct.lower()
    if g == c:
        return True
    threshold = 1 if len(c) <= 7 else 2
    return _levenshtein(g, c) <= threshold


def submit_answer(
    user_id: str, level_id: int, animal_index: int, answer: str,
    locale: str = "it", ad_revealed: bool = False,
) -> AnswerResponse | None:
    """Check an answer and update progress / coins / points.

    Returns None if level_id or animal_index is invalid.
    """
    correct_name = get_animal_name_at(level_id, animal_index, locale=locale)
    if correct_name is None:
        return None

    store = get_store()
    progress = store.ensure_progress(user_id)
    level_progress = progress.get(level_id)
    if level_progress is None or animal_index >= len(level_progress):
        return None

    is_correct = _is_fuzzy_match(answer, correct_name)
    coins_awarded = 0
    points_awarded = 0
    total_coins = store.get_coins(user_id)
    streak_bonus_coins = 0
    user_data = store.get_user(user_id) or {}
    current_streak = int(user_data.get("current_streak", 0) or 0)
    last_activity_date = user_data.get("last_activity_date")

    if is_correct and not level_progress[animal_index]:
        hints = store.get_hints(user_id)
        letters = store.get_letters(user_id)
        hints_used = hints.get(level_id, [0] * len(level_progress))[animal_index]
        letters_used = letters.get(level_id, [0] * len(level_progress))[animal_index]
        points_awarded = _calculate_points(ad_revealed, hints_used, letters_used)
        coins_awarded, total_coins, _, current_streak, last_activity_date, streak_bonus_coins = store.submit_answer_update(
            user_id, level_id, animal_index, COINS_PER_CORRECT, points_awarded,
        )

    return AnswerResponse(
        correct=is_correct,
        coins_awarded=coins_awarded,
        total_coins=total_coins,
        points_awarded=points_awarded,
        correct_answer=correct_name,
        current_streak=current_streak,
        last_activity_date=last_activity_date,
        streak_bonus_coins=streak_bonus_coins,
    )


def get_user_progress(user_id: str, locale: str = "it") -> dict[str, list[dict]]:
    """Return progress per level enriched with full animal objects."""
    store = get_store()
    progress = store.ensure_progress(user_id)
    hints = store.get_hints(user_id)
    letters = store.get_letters(user_id)
    result: dict[str, list[dict]] = {}
    for lid, bools in progress.items():
        detail = get_level_detail(lid, bools, locale=locale, hints=hints.get(lid), letters=letters.get(lid))
        if detail is not None:
            result[str(lid)] = [
                a.model_dump(by_alias=True) for a in detail.animals
            ]
    return result


def get_user_coins(user_id: str) -> int:
    """Return total coins for a user."""
    return get_store().get_coins(user_id)


def get_user_points(user_id: str) -> int:
    """Return total points for a user."""
    return get_store().get_points(user_id)


def get_user_level_guessed(user_id: str, level_id: int) -> list[bool]:
    """Return guessed list for a single level."""
    progress = get_store().ensure_progress(user_id)
    return progress.get(level_id, [])


def buy_hint(user_id: str, level_id: int, animal_index: int) -> BuyHintResponse:
    """Buy a hint for an animal. Raises ValueError on failure."""
    hints_revealed, total_coins = get_store().buy_hint(
        user_id, level_id, animal_index, settings.hint_costs_list,
    )
    return BuyHintResponse(total_coins=total_coins, hints_revealed=hints_revealed)


def reveal_letter(user_id: str, level_id: int, animal_index: int) -> RevealLetterResponse:
    """Reveal a letter for an animal. Raises ValueError on failure."""
    letters_revealed, total_coins = get_store().reveal_letter(
        user_id, level_id, animal_index,
        settings.REVEAL_LETTER_COST, settings.MAX_LETTER_REVEALS,
    )
    return RevealLetterResponse(total_coins=total_coins, letters_revealed=letters_revealed)


def count_completed_levels(user_id: str) -> int:
    """Return the number of levels where all animals are guessed."""
    return get_store().count_completed(user_id)
