"""
Progression Checker — evaluates double progression for each exercise.

Evidence basis (training_config.yaml):
- Double progression: increase reps within target range at target RIR.
  When all sets hit the TOP of the rep range at target RIR → increase load.
- Stall: no improvement in reps or weight over N sessions (default 2).
- Regression: average reps or weight dropped vs previous session.

What this module produces:
- A status per exercise: "progressing" | "ready_to_advance" | "stalled" | "regressing"
- A plain-English recommendation for the LLM to communicate to the user.

What this module does NOT do:
- It does not change the plan. The LLM agent does that.
- It does not make assumptions about why performance changed.
"""

import statistics

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Config
from src.models import WorkoutPlanExercise
from src.repositories.workout_repo import (
    get_active_plan_exercises,
    get_exercise_last_two_sessions,
)
from src.schemas.workout_schema import ExerciseProgressionSchema


def _load_progression_config() -> dict:
    """Load progression rules from training_config.yaml."""
    with open(Config.TRAINING_CONFIG_FILE) as f:
        config = yaml.safe_load(f)
    return config.get("progression", {})


def _avg(values: list[float | int]) -> float:
    """Safe average — returns 0.0 for empty list."""
    return statistics.mean(values) if values else 0.0


def _classify_progression(
    last_reps: float,
    last_weight: float,
    last_rir: float,
    prev_reps: float,
    prev_weight: float,
    target_reps_min: int,
    target_reps_max: int,
    target_rir_min: int,
    target_rir_max: int,
) -> tuple[str, str]:
    """
    Apply double progression logic and return (status, recommendation).

    Double progression rules:
    1. ready_to_advance: avg reps >= target_reps_max AND avg rir <= target_rir_max
       → Increase load next session
    2. progressing: reps increased vs previous session, within range
    3. regressing: reps or weight dropped vs previous session
    4. stalled: no change in reps or weight
    """
    # No previous data — can't assess yet
    if prev_reps == 0 and prev_weight == 0:
        return "progressing", "Not enough sessions to assess progression yet."

    # Ready to advance: hit top of rep range at or below target RIR
    if last_reps >= target_reps_max and last_rir <= target_rir_max:
        return (
            "ready_to_advance",
            f"All sets reached {target_reps_max}+ reps at RIR {last_rir:.0f}. "
            "Increase load by the recommended increment next session.",
        )

    # Regression: weight dropped OR reps dropped significantly
    if last_weight < prev_weight:
        return (
            "regressing",
            f"Weight dropped from {prev_weight:.1f}kg to {last_weight:.1f}kg. "
            "Check recovery, sleep, and nutrition before next session.",
        )
    if last_reps < prev_reps - 1:
        return (
            "regressing",
            f"Average reps dropped from {prev_reps:.1f} to {last_reps:.1f} at {last_weight:.1f}kg. "
            "Possible fatigue accumulation — monitor next session.",
        )

    # Load increase (progressive overload via load)
    if last_weight > prev_weight:
        return (
            "progressing",
            f"Load increased from {prev_weight:.1f}kg to {last_weight:.1f}kg ({last_reps:.1f} reps). "
            f"Build reps toward {target_reps_max} at this new load.",
        )

    # Stalled: same weight and reps within 0.5
    if abs(last_reps - prev_reps) < 0.5 and abs(last_weight - prev_weight) < 0.1:
        return (
            "stalled",
            f"No change in reps ({last_reps:.1f}) or weight ({last_weight:.1f}kg) "
            "over the last two sessions. Consider a technique check or deload.",
        )

    # Rep improvement at same load
    if last_reps > prev_reps:
        return (
            "progressing",
            f"Reps improved from {prev_reps:.1f} to {last_reps:.1f} at {last_weight:.1f}kg. "
            f"Continue adding reps toward {target_reps_max}.",
        )

    # Minor rep drop (< 1 rep) at same load
    return (
        "stalled",
        f"Maintained ~{last_reps:.1f} reps at {last_weight:.1f}kg. "
        f"Aim for {target_reps_max} reps next session.",
    )


async def check_progression(
    session: AsyncSession,
    user_id: int,
) -> list[ExerciseProgressionSchema]:
    """
    Check progression for all exercises in the user's active plan.

    Steps:
    1. Fetch all exercises from the active plan (with targets)
    2. For each exercise, compare last two sessions
    3. Apply double progression logic
    4. Return list of ExerciseProgressionSchema
    """
    plan_exercises: list[WorkoutPlanExercise] = await get_active_plan_exercises(
        session, user_id
    )

    if not plan_exercises:
        return []

    results: list[ExerciseProgressionSchema] = []

    for plan_ex in plan_exercises:
        exercise_id = plan_ex.exercise_id
        exercise_name = plan_ex.exercise.name if plan_ex.exercise else f"exercise_{exercise_id}"

        last_logs, prev_logs = await get_exercise_last_two_sessions(
            session, user_id, exercise_id
        )

        if not last_logs:
            continue  # Exercise never logged — skip

        # Compute averages for last session
        last_reps = _avg([log.reps for log in last_logs])
        last_weight = _avg([log.weight_kg for log in last_logs])
        last_rir = _avg([log.rir for log in last_logs])

        # Compute averages for previous session (may be empty)
        prev_reps = _avg([log.reps for log in prev_logs])
        prev_weight = _avg([log.weight_kg for log in prev_logs])

        status, recommendation = _classify_progression(
            last_reps=last_reps,
            last_weight=last_weight,
            last_rir=last_rir,
            prev_reps=prev_reps,
            prev_weight=prev_weight,
            target_reps_min=plan_ex.target_reps_min,
            target_reps_max=plan_ex.target_reps_max,
            target_rir_min=plan_ex.target_rir_min,
            target_rir_max=plan_ex.target_rir_max,
        )

        results.append(
            ExerciseProgressionSchema(
                exercise_name=exercise_name,
                exercise_id=exercise_id,
                last_session_avg_reps=round(last_reps, 1),
                last_session_avg_weight_kg=round(last_weight, 1),
                last_session_avg_rir=round(last_rir, 1),
                prev_session_avg_reps=round(prev_reps, 1),
                prev_session_avg_weight_kg=round(prev_weight, 1),
                target_reps_min=plan_ex.target_reps_min,
                target_reps_max=plan_ex.target_reps_max,
                target_rir_min=plan_ex.target_rir_min,
                target_rir_max=plan_ex.target_rir_max,
                progression_rule=plan_ex.progression_rule or "double_progression",
                status=status,
                recommendation=recommendation,
            )
        )

    # Sort by urgency: stalled/regressing first
    priority = {"regressing": 0, "stalled": 1, "ready_to_advance": 2, "progressing": 3}
    results.sort(key=lambda e: priority.get(e.status, 99))

    return results
