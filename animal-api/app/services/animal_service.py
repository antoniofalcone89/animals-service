"""Business logic for animal operations."""

import logging
from functools import lru_cache

from app.db.database import load_animals
from app.models.animal import Animal

logger = logging.getLogger(__name__)


def get_all_animals() -> list[Animal]:
    """Return all animals."""
    return list(load_animals())


def get_animals_by_level(level: int) -> list[Animal]:
    """Return animals filtered by rarity level."""
    return [a for a in load_animals() if a.level == level]


@lru_cache(maxsize=128)
def get_animal_by_name(name: str) -> Animal | None:
    """Return a single animal by name (case-insensitive)."""
    lower = name.lower()
    for animal in load_animals():
        if animal.name.lower() == lower:
            return animal
    return None
