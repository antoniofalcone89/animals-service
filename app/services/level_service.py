"""Business logic for quiz levels."""

import json
import logging
from functools import lru_cache
from pathlib import Path

from app.models.quiz import AnimalWithStatus, Level, LevelDetail, QuizAnimal

logger = logging.getLogger(__name__)

QUIZ_LEVELS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "quiz_levels.json"


@lru_cache(maxsize=1)
def _load_quiz_levels() -> list[dict]:
    """Load quiz levels from quiz_levels.json."""
    with open(QUIZ_LEVELS_FILE, "r") as f:
        return json.load(f)


def get_all_levels() -> list[Level]:
    """Return all levels with their animals."""
    raw_levels = _load_quiz_levels()
    return [
        Level(
            id=lvl["id"],
            title=lvl["title"],
            emoji=lvl["emoji"],
            animals=[
                QuizAnimal(id=a["id"], name=a["name"], emoji=a["emoji"], image_url=a["imageUrl"])
                for a in lvl["animals"]
            ],
        )
        for lvl in raw_levels
    ]


def get_level_detail(level_id: int, guessed: list[bool] | None = None) -> LevelDetail | None:
    """Return level detail with per-animal guessed status."""
    raw_levels = _load_quiz_levels()
    lvl = next((l for l in raw_levels if l["id"] == level_id), None)
    if lvl is None:
        return None

    animals = lvl["animals"]
    guessed = guessed or [False] * len(animals)
    animals_with_status = [
        AnimalWithStatus(
            id=a["id"], name=a["name"], emoji=a["emoji"], image_url=a["imageUrl"],
            guessed=guessed[i] if i < len(guessed) else False,
        )
        for i, a in enumerate(animals)
    ]
    return LevelDetail(
        id=lvl["id"],
        title=lvl["title"],
        emoji=lvl["emoji"],
        animals=animals_with_status,
    )


def get_animal_name_at(level_id: int, animal_index: int) -> str | None:
    """Return the animal name at the given index within a level, or None."""
    raw_levels = _load_quiz_levels()
    lvl = next((l for l in raw_levels if l["id"] == level_id), None)
    if lvl is None:
        return None
    animals = lvl["animals"]
    if 0 <= animal_index < len(animals):
        return animals[animal_index]["name"]
    return None


def get_level_animal_count(level_id: int) -> int:
    """Return the number of animals in a level."""
    raw_levels = _load_quiz_levels()
    lvl = next((l for l in raw_levels if l["id"] == level_id), None)
    if lvl is None:
        return 0
    return len(lvl["animals"])


def get_level_ids() -> list[int]:
    """Return all level IDs."""
    raw_levels = _load_quiz_levels()
    return [lvl["id"] for lvl in raw_levels]
