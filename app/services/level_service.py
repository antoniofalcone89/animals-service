"""Business logic for quiz levels."""

import json
import logging
from functools import lru_cache
from pathlib import Path

from app.db.database import load_animals
from app.models.quiz import AnimalWithStatus, Level, LevelDetail, QuizAnimal

logger = logging.getLogger(__name__)

LEVELS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "levels.json"

# Emoji mapping for animals in quiz context
ANIMAL_EMOJIS: dict[str, str] = {
    "Dog": "\U0001f415", "Cat": "\U0001f408", "Chicken": "\U0001f414",
    "Cow": "\U0001f404", "Sheep": "\U0001f411", "Pig": "\U0001f437",
    "Horse": "\U0001f434", "Goat": "\U0001f410", "Duck": "\U0001f986",
    "Pigeon": "\U0001f426", "Sparrow": "\U0001f426", "Rat": "\U0001f400",
    "Fox": "\U0001f98a", "Deer": "\U0001f98c", "Rabbit": "\U0001f407",
    "Squirrel": "\U0001f43f\ufe0f", "Raccoon": "\U0001f99d", "Hedgehog": "\U0001f994",
    "Badger": "\U0001f9a1", "Coyote": "\U0001f43a", "Eagle": "\U0001f985",
    "Owl": "\U0001f989", "Beaver": "\U0001f9ab", "Flamingo": "\U0001f9a9",
    "Red Panda": "\U0001f43e", "Koala": "\U0001f428", "Penguin": "\U0001f427",
    "Otter": "\U0001f9a6", "Sloth": "\U0001f9a5", "Chameleon": "\U0001f98e",
    "Porcupine": "\U0001f43e", "Toucan": "\U0001f426", "Capybara": "\U0001f43e",
    "Manta Ray": "\U0001f43e", "Platypus": "\U0001f43e", "Seahorse": "\U0001f43e",
    "Armadillo": "\U0001f43e", "Wolf": "\U0001f43a",
    "Snow Leopard": "\U0001f406", "Pangolin": "\U0001f43e",
    "Axolotl": "\U0001f43e", "Narwhal": "\U0001f40b", "Okapi": "\U0001f43e",
    "Clouded Leopard": "\U0001f406", "Quokka": "\U0001f43e",
    "Cassowary": "\U0001f43e", "Gharial": "\U0001f40a", "Saola": "\U0001f43e",
    "Fossa": "\U0001f43e", "Aye-Aye": "\U0001f43e", "Numbat": "\U0001f43e",
    "Dugong": "\U0001f43e", "Kakapo": "\U0001f99c",
    "Vaquita": "\U0001f42c", "Javan Rhino": "\U0001f98f",
    "Philippine Eagle": "\U0001f985", "Amur Leopard": "\U0001f406",
    "Sumatran Orangutan": "\U0001f9a7", "Red Wolf": "\U0001f43a",
    "Yangtze Finless Porpoise": "\U0001f42c",
    "Northern Hairy-Nosed Wombat": "\U0001f43e",
    "Cross River Gorilla": "\U0001f98d", "Hainan Gibbon": "\U0001f412",
}


@lru_cache(maxsize=1)
def _load_levels_metadata() -> list[dict]:
    """Load level metadata from levels.json."""
    with open(LEVELS_FILE, "r") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _build_level_animals() -> dict[int, list[tuple[int, str, str, str]]]:
    """Build mapping of level_id -> [(global_id, name, emoji, image_url), ...].

    Animals are ordered by their position in animals.json.
    """
    animals = load_animals()
    by_level: dict[int, list[tuple[int, str, str, str]]] = {}
    for i, animal in enumerate(animals):
        global_id = i + 1
        emoji = ANIMAL_EMOJIS.get(animal.name, "\U0001f43e")
        by_level.setdefault(animal.level, []).append(
            (global_id, animal.name, emoji, animal.image_url)
        )
    return by_level


def get_all_levels() -> list[Level]:
    """Return all levels with their animals."""
    metadata = _load_levels_metadata()
    level_animals = _build_level_animals()
    result = []
    for meta in metadata:
        level_id = meta["id"]
        animals = level_animals.get(level_id, [])
        quiz_animals = [
            QuizAnimal(id=gid, name=name, emoji=emoji, image_url=url)
            for gid, name, emoji, url in animals
        ]
        result.append(Level(
            id=level_id,
            title=meta["title"],
            emoji=meta["emoji"],
            animals=quiz_animals,
        ))
    return result


def get_level_detail(level_id: int, guessed: list[bool] | None = None) -> LevelDetail | None:
    """Return level detail with per-animal guessed status."""
    metadata = _load_levels_metadata()
    meta = next((m for m in metadata if m["id"] == level_id), None)
    if meta is None:
        return None

    level_animals = _build_level_animals()
    animals = level_animals.get(level_id, [])
    if not animals:
        return None

    guessed = guessed or [False] * len(animals)
    animals_with_status = [
        AnimalWithStatus(
            id=gid, name=name, emoji=emoji, image_url=url,
            guessed=guessed[i] if i < len(guessed) else False,
        )
        for i, (gid, name, emoji, url) in enumerate(animals)
    ]
    return LevelDetail(
        id=level_id,
        title=meta["title"],
        emoji=meta["emoji"],
        animals=animals_with_status,
    )


def get_animal_name_at(level_id: int, animal_index: int) -> str | None:
    """Return the animal name at the given index within a level, or None."""
    level_animals = _build_level_animals()
    animals = level_animals.get(level_id, [])
    if 0 <= animal_index < len(animals):
        return animals[animal_index][1]  # name
    return None


def get_level_animal_count(level_id: int) -> int:
    """Return the number of animals in a level."""
    level_animals = _build_level_animals()
    return len(level_animals.get(level_id, []))


def get_level_ids() -> list[int]:
    """Return all level IDs."""
    metadata = _load_levels_metadata()
    return [m["id"] for m in metadata]
