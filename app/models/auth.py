"""Pydantic models for authentication and user data."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class RegisterRequest(BaseModel):
    """Request schema for user registration (after Firebase client-side auth)."""

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    username: str = Field(..., min_length=2, max_length=30, description="Display name")
    photo_url: Optional[str] = Field(None, description="Profile photo URL hint from client")


class UpdateProfileRequest(BaseModel):
    """Request schema for profile update."""

    username: Optional[str] = Field(None, min_length=2, max_length=30, description="New display name")


class User(BaseModel):
    """Schema representing a user."""

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    id: str = Field(..., description="User ID (Firebase UID)")
    username: str = Field(..., description="Display name")
    email: Optional[str] = Field(None, description="Email address")
    total_coins: int = Field(0, description="Total coins earned")
    score: int = Field(0, description="Total score (points) earned")
    created_at: datetime = Field(..., description="Account creation timestamp")
    photo_url: Optional[str] = Field(None, description="Profile photo URL")
    current_streak: int = Field(0, description="Current daily streak in days")
    last_activity_date: Optional[str] = Field(None, description="Last streak activity date as ISO date (YYYY-MM-DD)")
    total_answers: int = Field(0, description="Total answer attempts (correct + wrong)")
    total_correct: int = Field(0, description="Total first-time correct answers")
    total_hints_used: int = Field(0, description="Total hints purchased across all levels")
    total_letters_used: int = Field(0, description="Total letter reveals across all levels")


class ErrorDetail(BaseModel):
    """Error detail with machine-readable code and human-readable message."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")


class ApiErrorResponse(BaseModel):
    """Error response matching the API spec format."""

    error: ErrorDetail
