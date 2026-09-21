"""
User and UserPreferences ORM models.

Schema decisions:
- experience_level is stored as a plain string (beginner/intermediate/advanced)
  rather than an Enum so the config YAML and DB stay in sync without migrations
  every time we add a level.
- equipment_available, preferred_exercises, disliked_exercises, limitations,
  dietary_preferences, allergies are stored as JSON arrays. This avoids
  unnecessary junction tables for simple list-of-strings data.
"""

from sqlalchemy import JSON, CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    age: Mapped[int] = mapped_column(nullable=False)
    gender: Mapped[str] = mapped_column(String(10), nullable=False)  # "male" | "female"
    height_cm: Mapped[float] = mapped_column(nullable=False)
    weight_kg: Mapped[float] = mapped_column(nullable=False)

    # "beginner" | "intermediate" | "advanced"
    experience_level: Mapped[str] = mapped_column(String(20), nullable=False)

    # "fat_loss" | "muscle_gain" | "maintenance" | "general_fitness"
    goal: Mapped[str] = mapped_column(String(30), nullable=False)

    training_days_per_week: Mapped[int] = mapped_column(nullable=False)
    session_duration_minutes: Mapped[int] = mapped_column(nullable=False, default=60)

    __table_args__ = (
        CheckConstraint("age >= 16 AND age <= 100", name="ck_users_age"),
        CheckConstraint("height_cm > 100 AND height_cm < 250", name="ck_users_height"),
        CheckConstraint("weight_kg > 30 AND weight_kg < 300", name="ck_users_weight"),
        CheckConstraint(
            "training_days_per_week BETWEEN 1 AND 7",
            name="ck_users_training_days",
        ),
        CheckConstraint(
            "gender IN ('male', 'female')",
            name="ck_users_gender",
        ),
        CheckConstraint(
            "experience_level IN ('beginner', 'intermediate', 'advanced')",
            name="ck_users_experience",
        ),
        CheckConstraint(
            "goal IN ('fat_loss', 'muscle_gain', 'maintenance', 'general_fitness')",
            name="ck_users_goal",
        ),
    )

    # ── Relationships ────────────────────────────────────────────────────────
    preferences: Mapped["UserPreferences"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    workout_plans: Mapped[list["WorkoutPlan"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    workout_sessions: Mapped[list["WorkoutSession"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    nutrition_profiles: Mapped[list["NutritionProfile"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    meal_plans: Mapped[list["MealPlan"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} name={self.name!r} goal={self.goal!r}>"


class UserPreferences(Base):
    """
    User's equipment, exercise preferences, dietary needs.
    All list fields are stored as JSON arrays for flexibility.
    """

    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    # Training preferences
    # JSON arrays of strings, e.g. ["barbell", "dumbbell", "cable", "machine"]
    equipment_available: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    preferred_exercises: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # exercise IDs
    disliked_exercises: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # exercise IDs
    limitations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # e.g. ["bad_knees"]

    # Nutrition preferences
    dietary_preferences: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # e.g. ["vegetarian"]
    allergies: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # e.g. ["nuts"]
    meals_per_day: Mapped[int] = mapped_column(nullable=False, default=3)

    # ── Relationships ────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship(back_populates="preferences")

    def __repr__(self) -> str:
        return f"<UserPreferences user_id={self.user_id}>"
