"""Animal API endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.models.animal import AnimalDetailResponse, AnimalListResponse, ErrorResponse
from app.services.animal_service import (
    get_all_animals,
    get_animal_by_name,
    get_animals_by_level,
)

logger = logging.getLogger(__name__)

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.get(
    "/animals",
    response_model=AnimalListResponse,
    responses={429: {"model": ErrorResponse}},
    summary="Get all animals",
    description="Retrieve all animals, optionally filtered by rarity level.",
)
@limiter.limit(settings.RATE_LIMIT)
async def list_animals(
    request: Request,
    level: int | None = Query(None, ge=1, le=10, description="Filter by rarity level (1-10)"),
) -> AnimalListResponse:
    """Get all animals with optional level filter."""
    if level is not None:
        animals = get_animals_by_level(level)
    else:
        animals = get_all_animals()
    logger.info("Returning %d animals (level filter=%s)", len(animals), level)
    return AnimalListResponse(data=animals, count=len(animals))


@router.get(
    "/animals/level/{level}",
    response_model=AnimalListResponse,
    responses={404: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
    summary="Get animals by rarity level",
    description="Retrieve all animals with a specific rarity level (1-10).",
)
@limiter.limit(settings.RATE_LIMIT)
async def animals_by_level(
    request: Request,
    level: int,
) -> AnimalListResponse:
    """Get all animals with a specific rarity level."""
    if level < 1 or level > 10:
        raise HTTPException(status_code=400, detail="Level must be between 1 and 10")
    animals = get_animals_by_level(level)
    return AnimalListResponse(data=animals, count=len(animals))


@router.get(
    "/animals/{name}",
    response_model=AnimalDetailResponse,
    responses={404: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
    summary="Get animal by name",
    description="Retrieve a specific animal by name (case-insensitive).",
)
@limiter.limit(settings.RATE_LIMIT)
async def animal_by_name(
    request: Request,
    name: str,
) -> AnimalDetailResponse:
    """Get a specific animal by name."""
    animal = get_animal_by_name(name)
    if animal is None:
        raise HTTPException(status_code=404, detail=f"Animal '{name}' not found")
    return AnimalDetailResponse(data=animal)


@router.get(
    "/health",
    summary="Health check",
    description="Check that the API is running.",
)
@limiter.limit(settings.RATE_LIMIT)
async def health_check(request: Request) -> dict:
    """Health check endpoint — no auth required."""
    return {"status": "healthy"}
