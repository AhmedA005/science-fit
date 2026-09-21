"""
Pydantic schemas for nutrition domain.
"""

from pydantic import BaseModel, ConfigDict


class NutritionTargetsSchema(BaseModel):
    """
    Calculated nutrition targets for a user.
    All values are deterministic — derived from Mifflin-St Jeor + config.
    """

    model_config = ConfigDict(from_attributes=True)

    bmr: float
    tdee: float
    calorie_target: float
    protein_target_g: float
    carb_target_g: float
    fat_target_g: float
    goal: str

    # Audit trail — what formula and inputs produced these numbers
    formula_used: str = "mifflin_st_jeor"
    activity_factor: float = 1.55
    activity_level: str = "moderately_active"
    goal_adjustment_kcal: float = 0.0
    protein_formula: str = ""
    citation_sources: list[str] = []

    # Honest caveats shown to user
    limitations: list[str] = [
        "Calorie estimates have inherent ±10-15% error",
        "Targets are starting points — adjust based on 2-4 weeks of observed weight change",
    ]
