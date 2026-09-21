"""
Pydantic schemas for workout domain.

Covers: exercise logs, volume summaries, progression checks,
and the plan context fed to the LLM.
"""

from pydantic import BaseModel, ConfigDict, Field


class ExerciseLogSchema(BaseModel):
    """One logged set — mirrors the exercise_logs table row."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    exercise_id: int
    exercise_name: str
    set_number: int
    weight_kg: float
    reps: int
    rir: int           # Reps in Reserve
    is_warmup: bool


class SessionSummarySchema(BaseModel):
    """Aggregated info for one workout session."""

    session_id: int
    session_date: str         # ISO date string
    plan_day_name: str
    duration_minutes: int | None
    total_working_sets: int   # excludes warmup sets
    logs: list[ExerciseLogSchema]


class MuscleVolumeSchema(BaseModel):
    """Weekly sets for a single muscle group."""

    muscle_name: str
    weekly_sets: int
    minimum_effective_volume: int  # from training_config.yaml
    maximum_recoverable_volume: int
    status: str  # "below_mev" | "in_range" | "above_mrv"


class ExerciseProgressionSchema(BaseModel):
    """
    Progression status for one exercise.
    Compares last session to previous session.
    """

    exercise_name: str
    exercise_id: int
    last_session_avg_reps: float
    last_session_avg_weight_kg: float
    last_session_avg_rir: float
    prev_session_avg_reps: float
    prev_session_avg_weight_kg: float
    target_reps_min: int
    target_reps_max: int
    target_rir_min: int
    target_rir_max: int
    progression_rule: str            # e.g. "double_progression"
    status: str                      # "progressing" | "stalled" | "ready_to_advance" | "regressing"
    recommendation: str              # human-readable next step


class WorkoutContextSchema(BaseModel):
    """
    Full workout context passed to the LLM agent.
    Everything calculated deterministically — the LLM doesn't recompute this.
    """

    recent_sessions: list[SessionSummarySchema] = Field(default_factory=list)
    volume_by_muscle: list[MuscleVolumeSchema] = Field(default_factory=list)
    progression_checks: list[ExerciseProgressionSchema] = Field(default_factory=list)
    sessions_analyzed: int = 0
    weeks_of_data: int = 0
    has_existing_plan: bool = False
    current_plan_name: str | None = None
