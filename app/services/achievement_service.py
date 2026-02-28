"""Achievement definitions and server-side evaluation logic."""

import logging

logger = logging.getLogger(__name__)

ALL_ACHIEVEMENTS: dict[str, dict] = {
    "first_correct": {
        "name": "First Step",
        "description": "First correct answer ever",
    },
    "level_perfect": {
        "name": "Perfectionist",
        "description": "Complete a level with 0 hints used",
    },
    "level_speed": {
        "name": "Speedster",
        "description": "Complete a level in under 3 minutes",
    },
    "streak_7": {
        "name": "On Fire",
        "description": "7-day streak",
    },
    "streak_30": {
        "name": "Unstoppable",
        "description": "30-day streak",
    },
    "coins_500": {
        "name": "Coin Collector",
        "description": "Accumulate 500 coins",
    },
    "all_levels": {
        "name": "Graduate",
        "description": "Complete all levels",
    },
    "daily_10": {
        "name": "Daily Regular",
        "description": "Complete 10 daily challenges",
    },
    "no_hints_10": {
        "name": "Sharp Eye",
        "description": "Answer 10 animals in a row with no hints",
    },
}


def get_achievement_definitions() -> list[dict]:
    """Return all achievement definitions with id, name, and description."""
    return [{"id": k, **v} for k, v in ALL_ACHIEVEMENTS.items()]


def evaluate_answer_achievements(
    uid: str,
    hints_used: int,
    letters_used: int,
    level_id: int,
    total_coins: int,
    current_streak: int,
    progress: dict[int, list[bool]],
) -> list[str]:
    """Evaluate achievements after a first-time correct answer.

    Returns a list of newly unlocked achievement IDs.
    ``level_speed`` is excluded — it requires session timing tracked client-side.
    """
    from app.db.user_store import get_store  # local import to avoid circular deps
    store = get_store()
    newly_unlocked: list[str] = []

    total_correct = sum(sum(1 for g in bools if g) for bools in progress.values())

    # first_correct
    if total_correct == 1:
        if store.unlock_achievement(uid, "first_correct"):
            newly_unlocked.append("first_correct")

    # level_perfect: level is fully complete and no hints or letters were used
    level_bools = progress.get(level_id, [])
    if level_bools and all(level_bools):
        level_hints = store.get_hints(uid).get(level_id, [])
        level_letters = store.get_letters(uid).get(level_id, [])
        if all(h == 0 for h in level_hints) and all(lt == 0 for lt in level_letters):
            if store.unlock_achievement(uid, "level_perfect"):
                newly_unlocked.append("level_perfect")

    # all_levels: every level is at least 80% complete
    if progress and all(
        bools and sum(bools) / len(bools) >= 0.8
        for bools in progress.values()
    ):
        if store.unlock_achievement(uid, "all_levels"):
            newly_unlocked.append("all_levels")

    # streak milestones
    if current_streak >= 7:
        if store.unlock_achievement(uid, "streak_7"):
            newly_unlocked.append("streak_7")
    if current_streak >= 30:
        if store.unlock_achievement(uid, "streak_30"):
            newly_unlocked.append("streak_30")

    # coins_500
    if total_coins >= 500:
        if store.unlock_achievement(uid, "coins_500"):
            newly_unlocked.append("coins_500")

    # no_hints_10: 10 consecutive first-time correct answers with no hints or letters
    user_data = store.get_user(uid) or {}
    if hints_used == 0 and letters_used == 0:
        new_count = int(user_data.get("consecutive_no_hint_correct", 0) or 0) + 1
        store.update_user(uid, consecutive_no_hint_correct=new_count)
        if new_count >= 10:
            if store.unlock_achievement(uid, "no_hints_10"):
                newly_unlocked.append("no_hints_10")
    else:
        store.update_user(uid, consecutive_no_hint_correct=0)

    return newly_unlocked


def evaluate_daily_challenge_achievement(uid: str) -> list[str]:
    """Evaluate achievements after the user completes a daily challenge.

    Increments ``daily_challenges_completed`` on the user and checks ``daily_10``.
    Returns a list of newly unlocked achievement IDs.
    """
    from app.db.user_store import get_store  # local import to avoid circular deps
    store = get_store()
    user_data = store.get_user(uid) or {}
    new_count = int(user_data.get("daily_challenges_completed", 0) or 0) + 1
    store.update_user(uid, daily_challenges_completed=new_count)

    newly_unlocked: list[str] = []
    if new_count >= 10:
        if store.unlock_achievement(uid, "daily_10"):
            newly_unlocked.append("daily_10")

    return newly_unlocked
