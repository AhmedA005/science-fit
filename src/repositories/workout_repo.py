"""
Workout repository — DB queries for sessions, logs, and plans.

Key design: volume calculations ALWAYS filter is_warmup=False.
This is enforced here so no service can accidentally count warmup sets.
"""

from datetime import date, timedelta

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models import (
    Exercise,
    ExerciseLog,
    WorkoutPlan,
    WorkoutPlanDay,
    WorkoutPlanExercise,
    WorkoutSession,
)
from src.schemas.workout_schema import ExerciseLogSchema, SessionSummarySchema


async def get_recent_sessions(
    session: AsyncSession,
    user_id: int,
    weeks: int = 4,
) -> list[SessionSummarySchema]:
    """
    Fetch the last `weeks` weeks of workout sessions with all logs.
    Warmup sets are excluded from working set counts.
    """
    cutoff = date.today() - timedelta(weeks=weeks)

    result = await session.execute(
        select(WorkoutSession)
        .where(
            and_(
                WorkoutSession.user_id == user_id,
                WorkoutSession.session_date >= cutoff,
            )
        )
        .options(
            selectinload(WorkoutSession.exercise_logs).selectinload(ExerciseLog.exercise),
            selectinload(WorkoutSession.plan_day),
        )
        .order_by(desc(WorkoutSession.session_date))
    )
    sessions = result.scalars().all()

    summaries: list[SessionSummarySchema] = []
    for ws in sessions:
        working_logs = [log for log in ws.exercise_logs if not log.is_warmup]

        log_schemas = [
            ExerciseLogSchema(
                id=log.id,
                exercise_id=log.exercise_id,
                exercise_name=log.exercise.name,
                set_number=log.set_number,
                weight_kg=log.weight_kg,
                reps=log.reps,
                rir=log.rir if log.rir is not None else 0,
                is_warmup=log.is_warmup,
            )
            for log in working_logs
        ]

        day_name = ws.plan_day.name if ws.plan_day else "Unknown"

        summaries.append(
            SessionSummarySchema(
                session_id=ws.id,
                session_date=ws.session_date.isoformat(),
                plan_day_name=day_name,
                duration_minutes=ws.duration_minutes,
                total_working_sets=len(working_logs),
                logs=log_schemas,
            )
        )

    return summaries


async def get_exercise_sets_by_muscle(
    session: AsyncSession,
    user_id: int,
    weeks: int = 1,
) -> dict[str, int]:
    """
    Return working sets per muscle name for the given week window.
    Used by volume_calculator to compare against MEV/MRV thresholds.

    Warmup sets are strictly excluded (is_warmup=False enforced here).
    """
    cutoff = date.today() - timedelta(weeks=weeks)

    # Import here to avoid circular
    from src.models import ExerciseMuscle, Muscle

    result = await session.execute(
        select(Muscle.name, func.count(ExerciseLog.id).label("set_count"))
        .join(ExerciseMuscle, ExerciseMuscle.muscle_id == Muscle.id)
        .join(Exercise, Exercise.id == ExerciseMuscle.exercise_id)
        .join(ExerciseLog, ExerciseLog.exercise_id == Exercise.id)
        .join(WorkoutSession, WorkoutSession.id == ExerciseLog.workout_session_id)
        .where(
            and_(
                WorkoutSession.user_id == user_id,
                WorkoutSession.session_date >= cutoff,
                ExerciseLog.is_warmup == False,  # noqa: E712 — SQLAlchemy requires ==
                ExerciseMuscle.role == "primary",  # count primary muscle involvement only
            )
        )
        .group_by(Muscle.name)
    )

    return {row.name: row.set_count for row in result.all()}


async def get_exercise_last_two_sessions(
    session: AsyncSession,
    user_id: int,
    exercise_id: int,
) -> tuple[list[ExerciseLog], list[ExerciseLog]]:
    """
    Return working logs for the last two sessions that included this exercise.
    Used by progression_checker to compare performance.
    Returns (last_session_logs, previous_session_logs).
    """
    # Find the two most recent sessions containing this exercise
    subq = (
        select(WorkoutSession.id, WorkoutSession.session_date)
        .join(ExerciseLog, ExerciseLog.workout_session_id == WorkoutSession.id)
        .where(
            and_(
                WorkoutSession.user_id == user_id,
                ExerciseLog.exercise_id == exercise_id,
                ExerciseLog.is_warmup == False,  # noqa: E712
            )
        )
        .distinct()
        .order_by(desc(WorkoutSession.session_date))
        .limit(2)
        .subquery()
    )

    result = await session.execute(
        select(ExerciseLog)
        .join(subq, subq.c.id == ExerciseLog.workout_session_id)
        .where(
            and_(
                ExerciseLog.exercise_id == exercise_id,
                ExerciseLog.is_warmup == False,  # noqa: E712
            )
        )
        .order_by(desc(subq.c.session_date), ExerciseLog.set_number)
    )
    all_logs = result.scalars().all()

    if not all_logs:
        return [], []

    # Split by session id — first group = most recent
    seen_sessions: list[int] = []
    by_session: dict[int, list[ExerciseLog]] = {}
    for log in all_logs:
        sid = log.workout_session_id
        if sid not in by_session:
            by_session[sid] = []
            seen_sessions.append(sid)
        by_session[sid].append(log)

    last = by_session.get(seen_sessions[0], [])
    prev = by_session.get(seen_sessions[1], []) if len(seen_sessions) > 1 else []
    return last, prev


async def get_active_plan_exercises(
    session: AsyncSession,
    user_id: int,
) -> list[WorkoutPlanExercise]:
    """
    Return all exercises in the user's active workout plan (with targets).
    Used by progression_checker to know the targets for each exercise.
    """
    result = await session.execute(
        select(WorkoutPlan)
        .where(
            and_(
                WorkoutPlan.user_id == user_id,
                WorkoutPlan.status == "active",
            )
        )
        .options(
            selectinload(WorkoutPlan.days).selectinload(WorkoutPlanDay.exercises).selectinload(WorkoutPlanExercise.exercise)
        )
        .limit(1)
    )
    plan = result.scalar_one_or_none()
    if plan is None:
        return []

    exercises: list[WorkoutPlanExercise] = []
    for day in plan.days:
        exercises.extend(day.exercises)
    return exercises


async def get_active_plan_name(
    session: AsyncSession, user_id: int
) -> str | None:
    """Return the name of the user's active plan, or None."""
    result = await session.execute(
        select(WorkoutPlan.name)
        .where(
            and_(
                WorkoutPlan.user_id == user_id,
                WorkoutPlan.status == "active",
            )
        )
        .limit(1)
    )
    row = result.first()
    return row[0] if row else None
