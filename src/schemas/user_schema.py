"""
Pydantic schemas for user domain.

These are data-transfer objects (DTOs) — not ORM models.
Used to validate and type data flowing between layers:
    DB (ORM) → Repository → Service → Agent
"""

from pydantic import BaseModel, ConfigDict, Field


class UserProfileSchema(BaseModel):
    """Core user data needed for calculations."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    age: int
    gender: str
    height_cm: float
    weight_kg: float
    experience_level: str  # beginner | intermediate | advanced
    goal: str              # fat_loss | muscle_gain | maintenance | general_fitness
    training_days_per_week: int
    session_duration_minutes: int


class UserPreferencesSchema(BaseModel):
    """User equipment and preference data."""

    model_config = ConfigDict(from_attributes=True)

    equipment_available: list[str] = Field(default_factory=list)
    preferred_exercises: list[str] = Field(default_factory=list)
    disliked_exercises: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    dietary_preferences: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    meals_per_day: int = 3


class FullUserContext(BaseModel):
    """Everything about a user needed by the training engine."""

    profile: UserProfileSchema
    preferences: UserPreferencesSchema
