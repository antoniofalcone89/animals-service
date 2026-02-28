"""Pydantic models for quiz, levels, and leaderboard."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class QuizAnimal(BaseModel):
    """Animal representation in quiz context."""

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    id: int = Field(..., description="Animal ID")
    name: str = Field(..., description="Animal name")
    image_url: Optional[str] = Field(None, description="URL to animal image")
    hints: list[str] = Field(default_factory=list, description="3 progressive hints")
    fun_facts: list[str] = Field(default_factory=list, description="2 fun facts")


class AnimalWithStatus(QuizAnimal):
    """Animal with guessed status for level detail view."""

    guessed: bool = Field(False, description="Whether the current user has guessed this animal")
    hints_revealed: int = Field(0, description="Number of hints revealed for this animal")
    letters_revealed: int = Field(0, description="Number of letters revealed for this animal")


class Level(BaseModel):
    """Level summary with its animals."""

    id: int = Field(..., description="Level ID")
    title: str = Field(..., description="Level title")
    animals: list[QuizAnimal] = Field(..., description="Animals in this level")


class LevelDetail(BaseModel):
    """Level detail with per-animal guessed status."""

    id: int = Field(..., description="Level ID")
    title: str = Field(..., description="Level title")
    animals: list[AnimalWithStatus] = Field(..., description="Animals with guessed status")


class AnswerRequest(BaseModel):
    """Request schema for submitting a quiz answer."""

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    level_id: int = Field(..., description="Level ID")
    animal_index: int = Field(..., ge=0, description="Zero-based index of the animal within the level")
    answer: str = Field(..., description="The user's guess (case-insensitive)")
    ad_revealed: bool = Field(False, description="True when player watched an ad to reveal the answer")
    combo_multiplier: float = Field(
        1.0,
        ge=1.0,
        le=2.0,
        description="Client-side combo multiplier (1.0–2.0). Validated server-side.",
    )


class AnswerResponse(BaseModel):
    """Response schema for a quiz answer submission."""

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    correct: bool = Field(..., description="Whether the answer was correct")
    coins_awarded: int = Field(..., description="Coins earned for this answer")
    total_coins: int = Field(..., description="User's updated total coin count")
    points_awarded: int = Field(..., description="Points earned for this answer")
    correct_answer: str = Field(..., description="The correct answer (always returned so the client can display proper spelling)")
    current_streak: int = Field(0, description="Current daily streak in days")
    last_activity_date: Optional[str] = Field(None, description="Last streak activity date as ISO date (YYYY-MM-DD)")
    streak_bonus_coins: int = Field(0, description="Streak bonus coins granted on the first correct answer of the day")
    combo_multiplier: float = Field(1.0, description="Combo multiplier applied to points for this answer")
    new_achievements: list[str] = Field(default_factory=list, description="Achievement IDs newly unlocked by this answer")


class BuyHintRequest(BaseModel):
    """Request schema for buying a hint."""

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    level_id: int = Field(..., description="Level ID")
    animal_index: int = Field(..., ge=0, description="Zero-based index of the animal within the level")


class BuyHintResponse(BaseModel):
    """Response schema for a hint purchase."""

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    total_coins: int = Field(..., description="Updated coin balance after purchase")
    hints_revealed: int = Field(..., description="Number of hints now revealed for this animal")


class RevealLetterRequest(BaseModel):
    """Request schema for revealing a letter."""

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    level_id: int = Field(..., description="Level ID")
    animal_index: int = Field(..., ge=0, description="Zero-based index of the animal within the level")


class RevealLetterResponse(BaseModel):
    """Response schema for a letter reveal."""

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    total_coins: int = Field(..., description="Updated coin balance after purchase")
    letters_revealed: int = Field(..., description="Number of letters now revealed for this animal")


class AchievementEntry(BaseModel):
    """A single unlocked achievement."""

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    id: str = Field(..., description="Achievement ID")
    unlocked_at: str = Field(..., description="ISO timestamp when the achievement was unlocked")


class LeaderboardEntry(BaseModel):
    """A single entry on the leaderboard."""

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    rank: int = Field(..., description="Rank position")
    user_id: str = Field(..., description="User ID")
    username: str = Field(..., description="Display name")
    total_points: int = Field(..., description="Total points earned")
    levels_completed: int = Field(..., description="Number of levels fully completed")
    photo_url: Optional[str] = Field(None, description="Profile photo URL")
    current_streak: int = Field(0, description="Current daily streak in days")
    achievements_count: int = Field(0, description="Number of achievements unlocked")


class StreakResponse(BaseModel):
    """Response schema for current user's streak."""

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    current_streak: int = Field(0, description="Current daily streak in days")
    last_activity_date: Optional[str] = Field(None, description="Last streak activity date as ISO date (YYYY-MM-DD)")


class ChallengeTodayResponse(BaseModel):
    """Response schema for today's daily challenge."""

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    date: str = Field(..., description="Challenge date in YYYY-MM-DD format")
    animals: list[QuizAnimal] = Field(..., description="Daily challenge animals")
    completed: bool = Field(False, description="Whether the user completed today's challenge")
    score: Optional[int] = Field(None, description="Final challenge score (null until completed)")


class ChallengeAnswerRequest(BaseModel):
    """Request schema for submitting a daily challenge answer."""

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    animal_index: int = Field(..., ge=0, description="Zero-based index within today's challenge animal list")
    answer: str = Field(..., description="The user's guess (case-insensitive)")
    ad_revealed: bool = Field(False, description="True when player watched an ad to reveal the answer")


class ChallengeLeaderboardEntry(BaseModel):
    """A single entry in the daily challenge leaderboard."""

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    rank: int = Field(..., description="Rank position")
    user_id: str = Field(..., description="User ID")
    username: str = Field(..., description="Display name")
    score: int = Field(..., description="Daily challenge score")
    completed_at: Optional[str] = Field(None, description="Completion timestamp in ISO format")
    photo_url: Optional[str] = Field(None, description="Profile photo URL")
