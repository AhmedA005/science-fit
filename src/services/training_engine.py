"""
Training Engine — orchestrates all deterministic calculations and produces
the complete context that the LLM agent receives.

This is the boundary between Layer 3 (deterministic calculations) and
Layer 4 (LLM personalization). Nothing from Layer 4 leaks into this file.

What this engine produces:
- FullUserContext (profile + preferences)
- WorkoutContextSchema (sessions, volume by muscle, progression checks)
- NutritionTargetsSchema (TDEE, macros)

The LLM receives these as structured data and uses them to:
- Explain progress to the user
- Suggest plan modifications
- Generate new plans within the evidence-based constraints
"""

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories import (
    get_active_plan_name,
    get_full_user_context,
    get_latest_nutrition_profile,
    get_recent_sessions,
)
from src.schemas import (
    FullUserContext,
    NutritionTargetsSchema,
    WorkoutContextSchema,
)
from src.services.nutrition_calculator import calculate_nutrition_targets
from src.services.progression_checker import check_progression
from src.services.volume_calculator import calculate_weekly_volume

logger = logging.getLogger(__name__)


@dataclass
class UserEngineContext:
    """
    The complete context produced by the training engine.
    Everything the LLM needs — nothing more.
    """

    user: FullUserContext
    workout: WorkoutContextSchema
    nutrition: NutritionTargetsSchema


class TrainingEngine:
    """
    Orchestrates all Layer 3 calculations for a given user.

    Usage:
        engine = TrainingEngine(session)
        context = await engine.build_context(user_id=1)
        # Pass context to the LLM agent
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def build_context(
        self,
        user_id: int,
        weeks_of_history: int = 4,
    ) -> UserEngineContext:
        """
        Build the full deterministic context for a user.

        Args:
            user_id: the user to build context for
            weeks_of_history: how many weeks of sessions to include (default 4)

        Raises:
            ValueError: if user not found

        Returns:
            UserEngineContext with all calculated data
        """
        # 1. Fetch user profile + preferences
        user_context = await get_full_user_context(self.session, user_id)
        if user_context is None:
            raise ValueError(f"User {user_id} not found")

        profile = user_context.profile
        logger.info(
            "Building context for user %d (%s, %s, %s)",
            user_id, profile.name, profile.experience_level, profile.goal,
        )

        # 2. Fetch recent sessions
        recent_sessions = await get_recent_sessions(
            self.session, user_id, weeks=weeks_of_history
        )

        # 3. Calculate weekly volume by muscle (last 1 week)
        volume_by_muscle = await calculate_weekly_volume(
            self.session, user_id,
            experience_level=profile.experience_level,
            weeks=1,
        )

        # 4. Check progression for all active plan exercises
        progression_checks = await check_progression(self.session, user_id)

        # 5. Get plan name
        plan_name = await get_active_plan_name(self.session, user_id)

        workout_context = WorkoutContextSchema(
            recent_sessions=recent_sessions,
            volume_by_muscle=volume_by_muscle,
            progression_checks=progression_checks,
            sessions_analyzed=len(recent_sessions),
            weeks_of_data=weeks_of_history,
            has_existing_plan=plan_name is not None,
            current_plan_name=plan_name,
        )

        # 6. Get or calculate nutrition targets
        nutrition = await get_latest_nutrition_profile(self.session, user_id)
        if nutrition is None:
            # No saved profile — calculate fresh (don't persist here, agent can trigger that)
            nutrition = calculate_nutrition_targets(profile)
            logger.info("No saved nutrition profile found — calculated fresh targets")

        logger.info(
            "Context built: %d sessions, %d muscles tracked, %d exercises checked",
            len(recent_sessions),
            len(volume_by_muscle),
            len(progression_checks),
        )

        return UserEngineContext(
            user=user_context,
            workout=workout_context,
            nutrition=nutrition,
        )

    def format_context_for_llm(self, context: UserEngineContext) -> str:
        """
        Format the engine context as a structured text block for the LLM system prompt.

        The LLM receives this as factual, pre-calculated data.
        It should reference these numbers — not recalculate them.
        """
        u = context.user.profile
        n = context.nutrition
        w = context.workout

        lines = [
            "=== SCIENCE-FIT USER CONTEXT (Pre-calculated — do not recalculate) ===",
            "",
            f"USER: {u.name} | Age: {u.age} | Gender: {u.gender}",
            f"Body: {u.weight_kg}kg, {u.height_cm}cm | Level: {u.experience_level}",
            f"Goal: {u.goal} | Training: {u.training_days_per_week}d/week",
            "",
            "--- NUTRITION TARGETS (Mifflin-St Jeor) ---",
            f"BMR: {n.bmr} kcal | TDEE: {n.tdee} kcal",
            f"Calorie target: {n.calorie_target} kcal ({n.goal_adjustment_kcal:+.0f} from TDEE)",
            f"Protein: {n.protein_target_g}g | Carbs: {n.carb_target_g}g | Fat: {n.fat_target_g}g",
            f"Formula: {n.formula_used} | Activity: {n.activity_level} (×{n.activity_factor})",
            f"Citations: {', '.join(n.citation_sources)}",
            "",
        ]

        if w.has_existing_plan:
            lines.append(f"CURRENT PLAN: {w.current_plan_name}")
        lines.append(f"Sessions analyzed: {w.sessions_analyzed} ({w.weeks_of_data} weeks)")
        lines.append("")

        if w.volume_by_muscle:
            lines.append("--- WEEKLY VOLUME BY MUSCLE ---")
            for m in w.volume_by_muscle:
                flag = ""
                if m.status == "below_mev":
                    flag = " ⚠️ BELOW MEV"
                elif m.status == "above_mrv":
                    flag = " ⚠️ ABOVE MRV"
                lines.append(
                    f"  {m.muscle_name}: {m.weekly_sets} sets "
                    f"(MEV={m.minimum_effective_volume}, MRV={m.maximum_recoverable_volume})"
                    f"{flag}"
                )
            lines.append("")

        if w.progression_checks:
            lines.append("--- EXERCISE PROGRESSION ---")
            for ex in w.progression_checks:
                lines.append(
                    f"  {ex.exercise_name}: {ex.status.upper()} | "
                    f"Last: {ex.last_session_avg_reps:.1f} reps @ "
                    f"{ex.last_session_avg_weight_kg:.1f}kg (RIR {ex.last_session_avg_rir:.1f}) | "
                    f"Rec: {ex.recommendation}"
                )
            lines.append("")

        lines.append("=== END CONTEXT ===")
        return "\n".join(lines)
