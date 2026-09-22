"""
LangChain / LangGraph Tools for Science-Fit.

Provides deterministic calculation and RAG retrieval tools that the agent
can invoke during reasoning turns.
"""

from typing import Optional
import yaml
from langchain_core.tools import tool

from src.config import Config
from src.rag.retriever import evidence_retriever
from src.schemas.user_schema import UserProfileSchema
from src.services.nutrition_calculator import calculate_nutrition_targets


@tool
def search_scientific_evidence(query: str, category: Optional[str] = None) -> str:
    """
    Search the peer-reviewed scientific literature database (Qdrant) for evidence
    on hypertrophy, training volume, progressive overload, or nutrition.

    Args:
        query: Natural language query (e.g. "optimal protein intake for fat loss", "hypertrophy rep ranges").
        category: Optional filter: either 'training' or 'nutrition'.

    Returns:
        Formatted citations and paper excerpts with exact citation IDs.
    """
    chunks = evidence_retriever.search(query=query, top_k=3, category=category)
    return evidence_retriever.format_evidence_for_prompt(chunks)


@tool
def get_training_guidelines(experience_level: str = "intermediate") -> str:
    """
    Retrieve evidence-based volume landmarks (MEV, Recommended, MRV) and RIR guidelines
    for a specific experience level (beginner, intermediate, advanced).

    Args:
        experience_level: 'beginner', 'intermediate', or 'advanced'.

    Returns:
        Formatted text containing volume limits and RIR rules from scientific consensus.
    """
    try:
        with open(Config.TRAINING_CONFIG_FILE, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
    except Exception as e:
        return f"Error loading training guidelines: {e}"

    level = experience_level.lower()
    vg = cfg.get("volume_guidelines", {}).get(level, {})
    if not vg:
        return f"No volume guidelines found for experience level '{experience_level}'."

    lines = [
        f"=== TRAINING GUIDELINES ({level.upper()}) ===",
        f"- Minimum Effective Volume (MEV): {vg.get('minimum_effective')} sets/week per muscle",
        f"- Recommended Range (MAV): {vg.get('recommended_range', [0, 0])[0]}-{vg.get('recommended_range', [0, 0])[1]} sets/week",
        f"- Maximum Recoverable Volume (MRV): {vg.get('maximum_recoverable')} sets/week",
        f"- Citations: {', '.join(vg.get('sources', []))}",
        "",
        "Per-session cap:",
        f"- Max sets per muscle/session: {cfg.get('volume_guidelines', {}).get('per_session', {}).get('max_sets_per_muscle', 10)} sets",
        "=== END GUIDELINES ===",
    ]
    return "\n".join(lines)


@tool
def calculate_hypothetical_macros(
    weight_kg: float,
    height_cm: float,
    age: int,
    gender: str,
    activity_level: str,
    goal: str,
) -> str:
    """
    Calculate hypothetical BMR, TDEE, and macro targets for a 'what-if' scenario
    (e.g., if a user wants to know what their calories/macros would be if they cut or bulk).

    Args:
        weight_kg: Bodyweight in kilograms.
        height_cm: Height in centimeters.
        age: Age in years.
        gender: 'male' or 'female'.
        activity_level: 'sedentary', 'light', 'moderate', 'very_active', or 'extra_active'.
        goal: 'fat_loss', 'maintenance', or 'muscle_gain'.

    Returns:
        Structured text with calculated BMR, TDEE, calories, and protein/carb/fat targets.
    """
    dummy_profile = UserProfileSchema(
        id=0,
        email="hypothetical@sciencefit.local",
        name="Hypothetical User",
        age=age,
        gender=gender.lower(),
        height_cm=height_cm,
        weight_kg=weight_kg,
        activity_level=activity_level.lower(),
        goal=goal.lower(),
        experience_level="intermediate",
        training_days_per_week=4,
    )

    targets = calculate_nutrition_targets(dummy_profile)
    lines = [
        f"=== HYPOTHETICAL NUTRITION TARGETS ({goal.upper()}) ===",
        f"- BMR: {targets.bmr} kcal | TDEE: {targets.tdee} kcal",
        f"- Calorie Target: {targets.calorie_target} kcal ({targets.goal_adjustment_kcal:+.0f} kcal adjustment)",
        f"- Protein: {targets.protein_target_g}g ({targets.protein_g_per_kg:.1f} g/kg)",
        f"- Carbohydrates: {targets.carb_target_g}g",
        f"- Fats: {targets.fat_target_g}g",
        f"- Scientific Citations: {', '.join(targets.citation_sources)}",
        "=== END HYPOTHETICAL TARGETS ===",
    ]
    return "\n".join(lines)


AGENT_TOOLS = [
    search_scientific_evidence,
    get_training_guidelines,
    calculate_hypothetical_macros,
]
