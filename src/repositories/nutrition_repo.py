"""
Nutrition repository — DB queries for nutrition profiles.
"""

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import NutritionProfile
from src.schemas.nutrition_schema import NutritionTargetsSchema


async def get_latest_nutrition_profile(
    session: AsyncSession, user_id: int
) -> NutritionTargetsSchema | None:
    """
    Return the most recent nutrition profile for a user.
    NutritionProfile is append-only — latest row is always current.
    """
    result = await session.execute(
        select(NutritionProfile)
        .where(NutritionProfile.user_id == user_id)
        .order_by(desc(NutritionProfile.created_at))
        .limit(1)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        return None

    # Extract audit trail from the JSON calculation_details field
    details = profile.calculation_details or {}

    return NutritionTargetsSchema(
        bmr=profile.bmr,
        tdee=profile.tdee,
        calorie_target=profile.calorie_target,
        protein_target_g=profile.protein_target_g,
        carb_target_g=profile.carb_target_g,
        fat_target_g=profile.fat_target_g,
        goal=profile.goal,
        formula_used=details.get("formula", "mifflin_st_jeor"),
        activity_factor=details.get("activity_factor", 1.55),
        activity_level=details.get("activity_level", "moderately_active"),
        goal_adjustment_kcal=details.get("goal_adjustment", 0.0),
        protein_formula=details.get("protein_formula", ""),
        citation_sources=details.get("citation_sources", []),
    )


async def save_nutrition_profile(
    session: AsyncSession,
    user_id: int,
    targets: NutritionTargetsSchema,
    calculation_details: dict,
) -> NutritionProfile:
    """
    Save a new nutrition profile snapshot (append-only).
    Always inserts a new row — never updates existing ones (audit trail).
    """
    profile = NutritionProfile(
        user_id=user_id,
        bmr=targets.bmr,
        tdee=targets.tdee,
        calorie_target=targets.calorie_target,
        protein_target_g=targets.protein_target_g,
        carb_target_g=targets.carb_target_g,
        fat_target_g=targets.fat_target_g,
        goal=targets.goal,
        calculation_details=calculation_details,
    )
    session.add(profile)
    await session.flush()
    return profile
