"""
Food and meal plan ORM models.

Design decisions:
- Food stores a snapshot of USDA nutritional data per 100g (canonical form).
  quantity_g in MealPlanItem then scales everything at query time.
- MealPlan is optional / suggestive — as decided in project scope, meal
  generation is a suggestion, not mandatory. A user always has a
  NutritionProfile (calorie/macro targets) even without a MealPlan.
- MealPlanItem stores pre-calculated macros (calories, protein, carb, fat)
  for the given quantity_g so the UI never needs to re-compute.
"""

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class Food(Base):
    """
    A food item from USDA FoodData Central (Foundation Foods + SR Legacy).
    All macro values are per 100g — scale by quantity_g when building meals.
    """

    __tablename__ = "foods"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Original USDA FoodData Central ID — allows tracing back to source data
    fdc_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    serving_size_g: Mapped[float] = mapped_column(nullable=False, default=100.0)
    serving_description: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Macros per 100g
    calories: Mapped[float] = mapped_column(nullable=False)
    protein_g: Mapped[float] = mapped_column(nullable=False)
    carbohydrate_g: Mapped[float] = mapped_column(nullable=False)
    fat_g: Mapped[float] = mapped_column(nullable=False)
    fiber_g: Mapped[float | None] = mapped_column(nullable=True)

    # Broad category for filtering (e.g. "Beef Products", "Vegetables")
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)

    __table_args__ = (
        CheckConstraint("calories >= 0", name="ck_foods_calories"),
        CheckConstraint("protein_g >= 0", name="ck_foods_protein"),
        CheckConstraint("carbohydrate_g >= 0", name="ck_foods_carbs"),
        CheckConstraint("fat_g >= 0", name="ck_foods_fat"),
    )

    # ── Relationships ────────────────────────────────────────────────────────
    meal_plan_items: Mapped[list["MealPlanItem"]] = relationship(back_populates="food")

    def __repr__(self) -> str:
        return f"<Food id={self.id} name={self.name!r} kcal={self.calories}/100g>"


class MealPlan(Base, TimestampMixin):
    """
    An optional, suggested daily meal plan for a user.

    Linked to a NutritionProfile so the plan targets are traceable.
    A user can have macro targets (NutritionProfile) without ever
    generating a MealPlan — meal planning is suggestive, not mandatory.
    """

    __tablename__ = "meal_plans"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    nutrition_profile_id: Mapped[int] = mapped_column(
        ForeignKey("nutrition_profiles.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    meals_per_day: Mapped[int] = mapped_column(nullable=False)

    # Agent reasoning: why was this meal plan structured this way?
    generation_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("meals_per_day BETWEEN 1 AND 8", name="ck_meal_plans_meals_per_day"),
    )

    # ── Relationships ────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship(back_populates="meal_plans")  # noqa: F821
    nutrition_profile: Mapped["NutritionProfile"] = relationship(  # noqa: F821
        back_populates="meal_plans"
    )
    meals: Mapped[list["MealPlanMeal"]] = relationship(
        back_populates="meal_plan",
        cascade="all, delete-orphan",
        order_by="MealPlanMeal.meal_number",
    )

    def __repr__(self) -> str:
        return f"<MealPlan id={self.id} name={self.name!r} meals={self.meals_per_day}>"


class MealPlanMeal(Base):
    """One named meal within a MealPlan (e.g. meal_number=1, name='Breakfast')."""

    __tablename__ = "meal_plan_meals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    meal_plan_id: Mapped[int] = mapped_column(
        ForeignKey("meal_plans.id", ondelete="CASCADE"), nullable=False
    )
    meal_number: Mapped[int] = mapped_column(nullable=False)   # 1, 2, 3...
    meal_name: Mapped[str] = mapped_column(String(60), nullable=False)  # "Breakfast"

    # ── Relationships ────────────────────────────────────────────────────────
    meal_plan: Mapped["MealPlan"] = relationship(back_populates="meals")
    items: Mapped[list["MealPlanItem"]] = relationship(
        back_populates="meal", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<MealPlanMeal meal_number={self.meal_number} name={self.meal_name!r}>"


class MealPlanItem(Base):
    """
    One food entry within a meal.

    Macros are pre-calculated and stored (not re-derived from Food each time)
    so the UI can sum them instantly without joins.
    """

    __tablename__ = "meal_plan_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    meal_plan_meal_id: Mapped[int] = mapped_column(
        ForeignKey("meal_plan_meals.id", ondelete="CASCADE"), nullable=False
    )
    food_id: Mapped[int] = mapped_column(
        ForeignKey("foods.id", ondelete="RESTRICT"), nullable=False
    )

    quantity_g: Mapped[float] = mapped_column(nullable=False)

    # Pre-calculated for this quantity (calories = food.calories * quantity_g / 100)
    calories: Mapped[float] = mapped_column(nullable=False)
    protein_g: Mapped[float] = mapped_column(nullable=False)
    carb_g: Mapped[float] = mapped_column(nullable=False)
    fat_g: Mapped[float] = mapped_column(nullable=False)

    __table_args__ = (
        CheckConstraint("quantity_g > 0", name="ck_meal_items_quantity"),
        CheckConstraint("calories >= 0", name="ck_meal_items_calories"),
    )

    # ── Relationships ────────────────────────────────────────────────────────
    meal: Mapped["MealPlanMeal"] = relationship(back_populates="items")
    food: Mapped["Food"] = relationship(back_populates="meal_plan_items")

    def __repr__(self) -> str:
        return (
            f"<MealPlanItem food_id={self.food_id} "
            f"qty={self.quantity_g}g kcal={self.calories:.0f}>"
        )
