"""
Nutrition Calculator — deterministic TDEE and macro calculations.

Evidence basis (nutrition_config.yaml):
- BMR: Mifflin-St Jeor equation (MIFFLIN-1990) — most validated for general population
- Activity factor: standard multipliers (sedentary → extremely active)
- Protein: ≥1.6 g/kg/day for hypertrophy (MORTON-2018, ISSN-PROTEIN-2017)
- Fat: minimum 20% of calories for hormonal health (IRAKI-2019)
- Carbs: remaining calories after protein and fat

Everything is deterministic — same inputs always produce same outputs.
The LLM never performs these calculations; it only interprets the results.
"""

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Config
from src.repositories.nutrition_repo import save_nutrition_profile
from src.schemas.nutrition_schema import NutritionTargetsSchema
from src.schemas.user_schema import UserProfileSchema


def _load_nutrition_config() -> dict:
    """Load nutrition parameters from nutrition_config.yaml."""
    with open(Config.NUTRITION_CONFIG_FILE, encoding="utf-8-sig") as f:
        return yaml.safe_load(f)


def _mifflin_st_jeor(weight_kg: float, height_cm: float, age: int, gender: str) -> float:
    """
    Mifflin-St Jeor BMR equation.
    Male:   BMR = 10W + 6.25H - 5A + 5
    Female: BMR = 10W + 6.25H - 5A - 161
    Citation: MIFFLIN-1990
    """
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + 5 if gender == "male" else base - 161


def _get_activity_factor(activity_level: str, config: dict) -> float:
    """Look up the activity multiplier from config."""
    factors = config.get("activity_factors", {})
    level = factors.get(activity_level, {})
    return level.get("value", 1.55)  # moderate active fallback


def _infer_activity_level(training_days: int) -> str:
    """
    Map training days per week to an activity level.
    Simple heuristic — the LLM can ask the user to confirm this.
    """
    if training_days <= 1:
        return "sedentary"
    elif training_days <= 3:
        return "lightly_active"
    elif training_days <= 5:
        return "moderately_active"
    elif training_days <= 6:
        return "very_active"
    else:
        return "extremely_active"


def _goal_calorie_adjustment(goal: str, config: dict) -> float:
    """
    Return the calorie adjustment for a given goal.
    Uses midpoint of the recommended range from config.
    """
    adjustments = config.get("calorie_adjustments", {})
    if goal == "fat_loss":
        deficit_range = adjustments.get("fat_loss", {}).get("deficit_range", [300, 500])
        return -sum(deficit_range) / 2   # negative = deficit
    elif goal == "muscle_gain":
        surplus_range = adjustments.get("muscle_gain", {}).get("surplus_range", [200, 400])
        return sum(surplus_range) / 2     # positive = surplus
    else:
        return 0.0  # maintenance or general_fitness


def _protein_target(weight_kg: float, goal: str, config: dict) -> float:
    """
    Calculate protein target in grams.
    Uses higher value for fat_loss to preserve muscle (ISSN-PROTEIN-2017).
    """
    macros = config.get("macro_guidelines", {}).get("protein", {})
    if goal == "fat_loss":
        g_per_kg = macros.get("fat_loss_g_per_kg", 2.0)
        label = f"{g_per_kg} g/kg (fat_loss — muscle preservation)"
    else:
        g_per_kg = macros.get("resistance_training_g_per_kg", 1.6)
        label = f"{g_per_kg} g/kg (resistance training)"
    return round(weight_kg * g_per_kg, 1), label


def calculate_nutrition_targets(
    profile: UserProfileSchema,
    activity_level: str | None = None,
) -> NutritionTargetsSchema:
    """
    Calculate TDEE and macro targets for a user. Fully deterministic.

    Args:
        profile: UserProfileSchema with weight, height, age, gender, goal, training_days
        activity_level: override the inferred activity level (optional)

    Returns:
        NutritionTargetsSchema with full audit trail
    """
    config = _load_nutrition_config()

    # Step 1: BMR
    bmr = round(_mifflin_st_jeor(profile.weight_kg, profile.height_cm, profile.age, profile.gender), 1)

    # Step 2: Activity factor → TDEE
    level = activity_level or _infer_activity_level(profile.training_days_per_week)
    factor = _get_activity_factor(level, config)
    tdee = round(bmr * factor, 1)

    # Step 3: Goal adjustment
    adjustment = _goal_calorie_adjustment(profile.goal, config)
    calorie_target = round(tdee + adjustment, 1)

    # Step 4: Protein
    protein_g, protein_label = _protein_target(profile.weight_kg, profile.goal, config)

    # Step 5: Fat (minimum 20% of calorie target)
    min_fat_pct = config.get("macro_guidelines", {}).get("fat", {}).get(
        "minimum_percent_of_calories", 0.20
    )
    fat_g = round((calorie_target * min_fat_pct) / 9, 1)

    # Step 6: Carbs fill remaining calories
    calories_from_protein = protein_g * 4
    calories_from_fat = fat_g * 9
    remaining = calorie_target - calories_from_protein - calories_from_fat
    carb_g = round(max(remaining, 0) / 4, 1)

    # Load limitations from config
    limitations = config.get("honest_limitations", [
        "Calorie estimates have inherent ±10-15% error",
        "Targets are starting points — adjust based on 2-4 weeks of observed weight change",
    ])

    return NutritionTargetsSchema(
        bmr=bmr,
        tdee=tdee,
        calorie_target=calorie_target,
        protein_target_g=protein_g,
        carb_target_g=carb_g,
        fat_target_g=fat_g,
        goal=profile.goal,
        formula_used="mifflin_st_jeor",
        activity_factor=factor,
        activity_level=level,
        goal_adjustment_kcal=adjustment,
        protein_formula=protein_label,
        citation_sources=["MIFFLIN-1990", "MORTON-2018", "ISSN-PROTEIN-2017", "IRAKI-2019"],
        limitations=limitations,
    )


async def calculate_and_save_nutrition(
    session: AsyncSession,
    user_id: int,
    profile: UserProfileSchema,
    activity_level: str | None = None,
) -> NutritionTargetsSchema:
    """
    Calculate targets and persist them as a new snapshot in the DB.
    Returns the calculated targets.
    """
    targets = calculate_nutrition_targets(profile, activity_level)

    # Build full audit trail for DB storage
    calculation_details = {
        "formula": targets.formula_used,
        "citation": "MIFFLIN-1990",
        "inputs": {
            "weight_kg": profile.weight_kg,
            "height_cm": profile.height_cm,
            "age": profile.age,
            "gender": profile.gender,
        },
        "bmr": targets.bmr,
        "activity_factor": targets.activity_factor,
        "activity_level": targets.activity_level,
        "tdee": targets.tdee,
        "goal_adjustment": targets.goal_adjustment_kcal,
        "final_calorie_target": targets.calorie_target,
        "protein_formula": targets.protein_formula,
        "citation_sources": targets.citation_sources,
    }

    await save_nutrition_profile(session, user_id, targets, calculation_details)
    return targets
