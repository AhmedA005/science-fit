"""
Exercise and Muscle ORM models.

Design decisions:
- Muscle is a separate table (not an Enum) because we may add muscles
  and their display names should be editable without migrations.
- ExerciseMuscle is an explicit junction table (not relationship secondary)
  because it carries a `role` field (primary / secondary).
- equipment and movement_pattern are plain strings referencing values defined
  in training_config.yaml — keeping schema and config in sync.
"""

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class Muscle(Base):
    """
    A muscle group that exercises can target.
    Examples: "Chest", "Quads", "Lats", "Anterior Deltoid"
    """

    __tablename__ = "muscles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    # Broader grouping: "Upper Body", "Lower Body", "Core"
    muscle_group: Mapped[str] = mapped_column(String(30), nullable=False)

    # ── Relationships ────────────────────────────────────────────────────────
    exercise_muscles: Mapped[list["ExerciseMuscle"]] = relationship(
        back_populates="muscle"
    )

    def __repr__(self) -> str:
        return f"<Muscle id={self.id} name={self.name!r}>"


class Exercise(Base):
    """
    A single exercise in the curated database.

    movement_pattern values: "squat", "hinge", "horizontal_push",
    "horizontal_pull", "vertical_push", "vertical_pull", "isolation", "carry", "core"

    equipment values: "barbell", "dumbbell", "cable", "machine",
    "bodyweight", "kettlebell", "resistance_band", "smith_machine"

    exercise_type: "compound" | "isolation"
    difficulty:    "beginner" | "intermediate" | "advanced"
    """

    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    movement_pattern: Mapped[str] = mapped_column(String(30), nullable=False)
    equipment: Mapped[str] = mapped_column(String(30), nullable=False)
    exercise_type: Mapped[str] = mapped_column(String(20), nullable=False)  # compound | isolation
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    bilateral: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    beginner_friendly: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        CheckConstraint(
            "exercise_type IN ('compound', 'isolation')",
            name="ck_exercises_type",
        ),
        CheckConstraint(
            "difficulty IN ('beginner', 'intermediate', 'advanced')",
            name="ck_exercises_difficulty",
        ),
    )

    # ── Relationships ────────────────────────────────────────────────────────
    exercise_muscles: Mapped[list["ExerciseMuscle"]] = relationship(
        back_populates="exercise", cascade="all, delete-orphan"
    )
    workout_plan_exercises: Mapped[list["WorkoutPlanExercise"]] = relationship(  # noqa: F821
        back_populates="exercise"
    )
    exercise_logs: Mapped[list["ExerciseLog"]] = relationship(  # noqa: F821
        back_populates="exercise"
    )

    def __repr__(self) -> str:
        return f"<Exercise id={self.id} name={self.name!r} type={self.exercise_type!r}>"


class ExerciseMuscle(Base):
    """
    Junction table: Exercise ↔ Muscle with a role field.

    role: "primary" — the main muscle being trained
          "secondary" — meaningfully involved but not the focus
    """

    __tablename__ = "exercise_muscles"

    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"), primary_key=True
    )
    muscle_id: Mapped[int] = mapped_column(
        ForeignKey("muscles.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)  # "primary" | "secondary"

    __table_args__ = (
        CheckConstraint("role IN ('primary', 'secondary')", name="ck_exercise_muscles_role"),
        UniqueConstraint("exercise_id", "muscle_id", name="uq_exercise_muscle"),
    )

    # ── Relationships ────────────────────────────────────────────────────────
    exercise: Mapped["Exercise"] = relationship(back_populates="exercise_muscles")
    muscle: Mapped["Muscle"] = relationship(back_populates="exercise_muscles")

    def __repr__(self) -> str:
        return (
            f"<ExerciseMuscle exercise_id={self.exercise_id} "
            f"muscle_id={self.muscle_id} role={self.role!r}>"
        )
