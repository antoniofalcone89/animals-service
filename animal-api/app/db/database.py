"""Data access layer for loading animal data from JSON."""

import json
import logging
from functools import lru_cache
from pathlib import Path

from app.models.animal import Animal

logger = logging.getLogger(__name__)

DATA_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "animals.json"


@lru_cache(maxsize=1)
def load_animals() -> tuple[Animal, ...]:
    """Load all animals from the JSON data file.

    Returns a tuple (hashable for lru_cache) of Animal objects.
    """
    try:
        with open(DATA_FILE, "r") as f:
            raw = json.load(f)
        animals = tuple(Animal(**item) for item in raw)
        logger.info("Loaded %d animals from %s", len(animals), DATA_FILE)
        return animals
    except FileNotFoundError:
        logger.error("Animal data file not found: %s", DATA_FILE)
        return ()
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in animal data file: %s", e)
        return ()


def clear_cache() -> None:
    """Clear the animal data cache."""
    load_animals.cache_clear()
