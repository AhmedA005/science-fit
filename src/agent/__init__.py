"""
Science-Fit Agent Module — Layer 4 (LangGraph Personalization & Orchestration).
"""

from src.agent.llm import coach_llm, get_llm, strict_llm
from src.agent.prompts import BASE_COACH_SYSTEM_PROMPT, INTENT_ROUTER_SYSTEM_PROMPT, build_coach_system_message
from src.agent.state import FitnessAgentState
from src.agent.tools import (
    AGENT_TOOLS,
    calculate_hypothetical_macros,
    get_training_guidelines,
    search_scientific_evidence,
)

__all__ = [
    "FitnessAgentState",
    "get_llm",
    "coach_llm",
    "strict_llm",
    "BASE_COACH_SYSTEM_PROMPT",
    "INTENT_ROUTER_SYSTEM_PROMPT",
    "build_coach_system_message",
    "AGENT_TOOLS",
    "search_scientific_evidence",
    "get_training_guidelines",
    "calculate_hypothetical_macros",
]
