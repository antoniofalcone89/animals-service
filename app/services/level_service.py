"""Business logic for quiz levels."""

import json
import logging
from functools import lru_cache
from pathlib import Path

from app.models.quiz import AnimalWithStatus, Level, LevelDetail, QuizAnimal

logger = logging.getLogger(__name__)

QUIZ_LEVELS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "quiz_levels.json"
TRANSLATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "translations"

DEFAULT_LOCALE = "it"


@lru_cache(maxsize=1)
def _load_quiz_levels() -> list[dict]:
    """Load quiz levels from quiz_levels.json."""
    with open(QUIZ_LEVELS_FILE, "r") as f:
        return json.load(f)


@lru_cache(maxsize=4)
def _load_translations(locale: str) -> dict | None:
    """Load translation file for a locale, or None if not available."""
    path = TRANSLATIONS_DIR / f"{locale}.json"
    if not path.exists():
        return None
    with open(path, "r") as f:
        return json.load(f)


def _translate_animal_name(animal_id: int, english_name: str, locale: str) -> str:
    """Resolve the localized name for an animal."""
    if locale == "en":
        return english_name
    translations = _load_translations(locale)
    if translations is None:
        return english_name
    return translations.get("animals", {}).get(str(animal_id), english_name)


def _translate_level_title(level_id: int, english_title: str, locale: str) -> str:
    """Resolve the localized title for a level."""
    if locale == "en":
        return english_title
    translations = _load_translations(locale)
    if translations is None:
        return english_title
    return translations.get("levels", {}).get(str(level_id), english_title)


def _translate_hints(animal_id: int, locale: str) -> list[str]:
    """Resolve the localized hints for an animal."""
    translations = _load_translations(locale)
    if translations is None:
        # Fall back to English hints
        translations = _load_translations("en")
    if translations is None:
        return []
    return translations.get("hints", {}).get(str(animal_id), [])


def _translate_fun_facts(animal_id: int, locale: str) -> list[str]:
    """Resolve the localized fun facts for an animal."""
    translations = _load_translations(locale)
    if translations is None:
        # Fall back to English fun facts
        translations = _load_translations("en")
    if translations is None:
        return []
    return translations.get("funFacts", {}).get(str(animal_id), [])


def get_all_levels(locale: str = DEFAULT_LOCALE) -> list[Level]:
    """Return all levels with their animals."""
    raw_levels = _load_quiz_levels()
    return [
        Level(
            id=lvl["id"],
            title=_translate_level_title(lvl["id"], lvl["title"], locale),
            animals=[
                QuizAnimal(
                    id=a["id"],
                    name=_translate_animal_name(a["id"], a["name"], locale),
                    image_url=a["imageUrl"],
                    hints=_translate_hints(a["id"], locale),
                    fun_facts=_translate_fun_facts(a["id"], locale),
                )
                for a in lvl["animals"]
            ],
        )
        for lvl in raw_levels
    ]


def get_level_detail(
    level_id: int,
    guessed: list[bool] | None = None,
    locale: str = DEFAULT_LOCALE,
    hints: list[int] | None = None,
    letters: list[int] | None = None,
) -> LevelDetail | None:
    """Return level detail with per-animal guessed status, hints, and letters revealed."""
    raw_levels = _load_quiz_levels()
    lvl = next((l for l in raw_levels if l["id"] == level_id), None)
    if lvl is None:
        return None

    animals = lvl["animals"]
    guessed = guessed or [False] * len(animals)
    animals_with_status = [
        AnimalWithStatus(
            id=a["id"],
            name=_translate_animal_name(a["id"], a["name"], locale),
            image_url=a["imageUrl"],
            hints=_translate_hints(a["id"], locale),
            fun_facts=_translate_fun_facts(a["id"], locale),
            guessed=guessed[i] if i < len(guessed) else False,
            hints_revealed=hints[i] if hints and i < len(hints) else 0,
            letters_revealed=letters[i] if letters and i < len(letters) else 0,
        )
        for i, a in enumerate(animals)
    ]
    return LevelDetail(
        id=lvl["id"],
        title=_translate_level_title(lvl["id"], lvl["title"], locale),
        animals=animals_with_status,
    )


def get_animal_name_at(level_id: int, animal_index: int, locale: str = DEFAULT_LOCALE) -> str | None:
    """Return the localized animal name at the given index within a level, or None."""
    raw_levels = _load_quiz_levels()
    lvl = next((l for l in raw_levels if l["id"] == level_id), None)
    if lvl is None:
        return None
    animals = lvl["animals"]
    if 0 <= animal_index < len(animals):
        a = animals[animal_index]
        return _translate_animal_name(a["id"], a["name"], locale)
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
