"""
Volume Calculator — determines weekly sets per muscle and flags deviations.

Evidence basis:
- MEV/MRV thresholds come from training_config.yaml (sourced from Schoenfeld 2017, ACSM 2009)
- Only PRIMARY muscle involvement is counted (secondary muscles are bonus stimulus)
- Warmup sets are NEVER counted (enforced in the repository layer)

Key distinction:
- This module does NOT decide what to do about a volume issue.
  It just reports: "This muscle has X sets — that's below MEV / in range / above MRV."
- The LLM decides how to adjust the plan based on this report.
"""

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Config
from src.repositories.workout_repo import get_exercise_sets_by_muscle
from src.schemas.workout_schema import MuscleVolumeSchema


def _load_volume_thresholds(experience_level: str) -> dict:
    """
    Load MEV/MRV for the given experience level from training_config.yaml.
    Returns dict with keys: minimum_effective, maximum_recoverable.
    """
    with open(Config.TRAINING_CONFIG_FILE, encoding="utf-8-sig") as f:
        config = yaml.safe_load(f)

    level_config = config["volume_guidelines"].get(
        experience_level,
        config["volume_guidelines"]["intermediate"],  # safe fallback
    )
    return {
        "minimum_effective": level_config["minimum_effective"],
        "maximum_recoverable": level_config["maximum_recoverable"],
    }


def _classify_volume(sets: int, mev: int, mrv: int) -> str:
    """Return a status string based on where sets falls relative to MEV/MRV."""
    if sets < mev:
        return "below_mev"
    if sets > mrv:
        return "above_mrv"
    return "in_range"


async def calculate_weekly_volume(
    session: AsyncSession,
    user_id: int,
    experience_level: str,
    weeks: int = 1,
) -> list[MuscleVolumeSchema]:
    """
    Calculate weekly sets per muscle for the given user over the last `weeks` weeks.

    Steps:
    1. Query DB for sets per primary muscle (warmup excluded by repo)
    2. Load MEV/MRV thresholds from config
    3. Classify each muscle as below_mev / in_range / above_mrv
    4. Return sorted list (below_mev first — most urgent)

    Args:
        session: async DB session
        user_id: the user to analyze
        experience_level: "beginner" | "intermediate" | "advanced"
        weeks: how many weeks back to look (default 1)

    Returns:
        List of MuscleVolumeSchema, sorted by urgency (below_mev first)
    """
    thresholds = _load_volume_thresholds(experience_level)
    mev = thresholds["minimum_effective"]
    mrv = thresholds["maximum_recoverable"]

    sets_by_muscle = await get_exercise_sets_by_muscle(session, user_id, weeks=weeks)

    results: list[MuscleVolumeSchema] = []
    for muscle_name, weekly_sets in sets_by_muscle.items():
        status = _classify_volume(weekly_sets, mev, mrv)
        results.append(
            MuscleVolumeSchema(
                muscle_name=muscle_name,
                weekly_sets=weekly_sets,
                minimum_effective_volume=mev,
                maximum_recoverable_volume=mrv,
                status=status,
            )
        )

    # Sort: below_mev first (most urgent), then above_mrv, then in_range
    priority = {"below_mev": 0, "above_mrv": 1, "in_range": 2}
    results.sort(key=lambda m: (priority[m.status], m.muscle_name))

    return results


def summarize_volume(volume_data: list[MuscleVolumeSchema]) -> dict:
    """
    Return a quick summary dict for logging and LLM context.
    Example: {"below_mev": ["Hamstrings"], "above_mrv": [], "in_range": ["Chest", ...]}
    """
    summary: dict[str, list[str]] = {"below_mev": [], "above_mrv": [], "in_range": []}
    for m in volume_data:
        summary[m.status].append(m.muscle_name)
    return summary
