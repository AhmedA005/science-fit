"""
Nutrition-related ORM models: NutritionProfile.

Design decisions:
- NutritionProfile is a snapshot: when a user's weight/goal changes,
  we create a NEW profile rather than overwriting. This preserves history
  and lets us show how targets have changed over time.
- calculation_details (JSONB) stores the full formula inputs and outputs
  (BMR formula, activity factor used, deficit/surplus applied) so the
  user and developer can audit every number.
- Meal planning models are in food.py alongside the Food model since
  MealPlanItem references Food.
"""

from sqlalchemy import CheckConstraint, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class NutritionProfile(Base, TimestampMixin):
    """
    A calculated nutrition target for a user at a point in time.

    Created by the deterministic Mifflin-St Jeor calculation in
    nutrition_service.py. The LLM never writes to this table directly.

    calculation_details example:
    {
      "formula": "mifflin_st_jeor",
      "citation": "MIFFLIN-1990",
      "inputs": {
        "weight_kg": 80, "height_cm": 178, "age": 25, "sex": "male"
      },
      "bmr": 1876.5,
      "activity_factor": 1.55,
      "activity_level": "moderately_active",
      "tdee": 2908.6,
      "goal_adjustment": -400,
      "final_calorie_target": 2508.6,
      "protein_formula": "1.8 g/kg (fat_loss rate)",
      "citation_sources": ["MIFFLIN-1990", "MORTON-2018", "ISSN-PROTEIN-2017"]
    }
    """

    __tablename__ = "nutrition_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Calculated values (all deterministic — no LLM involvement)
    bmr: Mapped[float] = mapped_column(nullable=False)
    tdee: Mapped[float] = mapped_column(nullable=False)
    calorie_target: Mapped[float] = mapped_column(nullable=False)
    protein_target_g: Mapped[float] = mapped_column(nullable=False)
    carb_target_g: Mapped[float] = mapped_column(nullable=False)
    fat_target_g: Mapped[float] = mapped_column(nullable=False)

    # "fat_loss" | "muscle_gain" | "maintenance"
    goal: Mapped[str] = mapped_column(String(30), nullable=False)

    # Full audit trail: formula used, inputs, intermediate values, sources
    calculation_details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        CheckConstraint("bmr > 0", name="ck_nutrition_bmr"),
        CheckConstraint("tdee > 0", name="ck_nutrition_tdee"),
        CheckConstraint("calorie_target > 0", name="ck_nutrition_calories"),
        CheckConstraint("protein_target_g > 0", name="ck_nutrition_protein"),
        CheckConstraint(
            "goal IN ('fat_loss', 'muscle_gain', 'maintenance')",
            name="ck_nutrition_goal",
        ),
    )

    # ── Relationships ────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship(back_populates="nutrition_profiles")  # noqa: F821
    meal_plans: Mapped[list["MealPlan"]] = relationship(  # noqa: F821
        back_populates="nutrition_profile"
    )

    def __repr__(self) -> str:
        return (
            f"<NutritionProfile user_id={self.user_id} "
            f"calories={self.calorie_target:.0f} "
            f"P={self.protein_target_g:.0f}g C={self.carb_target_g:.0f}g F={self.fat_target_g:.0f}g>"
        )
