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


class ErrorDetail(BaseModel):
    """Error detail with machine-readable code and human-readable message."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")


class ApiErrorResponse(BaseModel):
    """Error response matching the API spec format."""

    error: ErrorDetail
