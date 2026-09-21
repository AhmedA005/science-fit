"""
Import all ORM models here so that:
1. Alembic can auto-detect all tables from a single import.
2. SQLAlchemy relationship resolution works (all models in memory together).

Usage in alembic/env.py:
    import src.models  # noqa — triggers all model imports
    from src.models.base import Base
    target_metadata = Base.metadata
"""

from src.models.base import Base, TimestampMixin
from src.models.exercise import Exercise, ExerciseMuscle, Muscle
from src.models.food import Food, MealPlan, MealPlanItem, MealPlanMeal
from src.models.nutrition import NutritionProfile
from src.models.user import User, UserPreferences
from src.models.workout import (
    ExerciseLog,
    WorkoutPlan,
    WorkoutPlanDay,
    WorkoutPlanExercise,
    WorkoutSession,
)

__all__ = [
    "Base",
    "TimestampMixin",
    "User",
    "UserPreferences",
    "Muscle",
    "Exercise",
    "ExerciseMuscle",
    "WorkoutPlan",
    "WorkoutPlanDay",
    "WorkoutPlanExercise",
    "WorkoutSession",
    "ExerciseLog",
    "NutritionProfile",
    "Food",
    "MealPlan",
    "MealPlanMeal",
    "MealPlanItem",
]
