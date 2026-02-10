"""Pydantic models for animal data."""

from typing import Optional

from pydantic import BaseModel, Field


class Animal(BaseModel):
    """Schema representing an animal."""

    name: str = Field(..., description="Animal name")
    level: int = Field(..., ge=1, le=10, description="Rarity level 1-10 (1=common, 10=rare)")
    image_url: str = Field(..., description="URL to animal image")
    description: Optional[str] = Field(None, description="Animal description")
    scientific_name: Optional[str] = Field(None, description="Scientific name")


class AnimalListResponse(BaseModel):
    """Response schema for a list of animals."""

    success: bool = True
    data: list[Animal]
    count: int


class AnimalDetailResponse(BaseModel):
    """Response schema for a single animal."""

    success: bool = True
    data: Animal


class ErrorResponse(BaseModel):
    """Response schema for errors."""

    success: bool = False
    error: str
    detail: Optional[str] = None
