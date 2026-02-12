"""Pydantic models for quiz, levels, and leaderboard."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class QuizAnimal(BaseModel):
    """Animal representation in quiz context."""

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    id: int = Field(..., description="Animal ID")
    name: str = Field(..., description="Animal name")
    emoji: str = Field(..., description="Animal emoji")
    image_url: str = Field(..., description="URL to animal image")


class AnimalWithStatus(QuizAnimal):
    """Animal with guessed status for level detail view."""

    guessed: bool = Field(False, description="Whether the current user has guessed this animal")


class Level(BaseModel):
    """Level summary with its animals."""

    id: int = Field(..., description="Level ID")
    title: str = Field(..., description="Level title")
    emoji: str = Field(..., description="Level emoji")
    animals: list[QuizAnimal] = Field(..., description="Animals in this level")


class LevelDetail(BaseModel):
    """Level detail with per-animal guessed status."""

    id: int = Field(..., description="Level ID")
    title: str = Field(..., description="Level title")
    emoji: str = Field(..., description="Level emoji")
    animals: list[AnimalWithStatus] = Field(..., description="Animals with guessed status")


class AnswerRequest(BaseModel):
    """Request schema for submitting a quiz answer."""

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    level_id: int = Field(..., description="Level ID")
    animal_index: int = Field(..., ge=0, description="Zero-based index of the animal within the level")
    answer: str = Field(..., description="The user's guess (case-insensitive)")


class AnswerResponse(BaseModel):
    """Response schema for a quiz answer submission."""

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    correct: bool = Field(..., description="Whether the answer was correct")
    coins_awarded: int = Field(..., description="Coins earned for this answer")
    total_coins: int = Field(..., description="User's updated total coin count")
    correct_answer: Optional[str] = Field(None, description="The correct answer (only returned when wrong)")


class LeaderboardEntry(BaseModel):
    """A single entry on the leaderboard."""

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    rank: int = Field(..., description="Rank position")
    user_id: str = Field(..., description="User ID")
    username: str = Field(..., description="Display name")
    total_coins: int = Field(..., description="Total coins earned")
    levels_completed: int = Field(..., description="Number of levels fully completed")
