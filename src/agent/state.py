"""
Agent State Definition for Science-Fit.

Defines the typed dictionary that flows through all nodes in the LangGraph workflow.
LangGraph uses this state to pass conversation history, deterministic metrics
from the TrainingEngine, retrieved scientific literature, and validation flags.
"""

from typing import Annotated, Sequence
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from src.rag.retriever import EvidenceChunk
from src.schemas import (
    FullUserContext,
    NutritionTargetsSchema,
    WorkoutContextSchema,
)


class FitnessAgentState(TypedDict, total=False):
    """
    Central state object for the Science-Fit LangGraph agent.

    Using TypedDict allows individual nodes in the graph to return partial
    dictionaries updating only the specific keys they are responsible for.
    """

    # ── Conversation & Identifiers ───────────────────────────────────────────
    # Sequence of LangChain messages with reducer that appends new messages
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # Target user ID whose profile & workout history are being coached
    user_id: int

    # Full user profile (demographics, fitness goal, experience) and preferences
    user_context: FullUserContext | None

    # Workout history analytics (muscle volumes vs MEV/MRV, progression checks)
    workout_context: WorkoutContextSchema | None

    # Pre-calculated nutrition targets (BMR, TDEE, macros, calorie goal)
    nutrition_targets: NutritionTargetsSchema | None

    # Pre-formatted text summary of the engine context for prompt injection
    engine_context_text: str | None

    # ── Intent Routing & RAG Evidence ────────────────────────────────────────
    # Classified user intent: e.g. "workout_review", "nutrition_guidance", "scientific_inquiry", "general_chat"
    intent: str | None

    # Raw retrieved scientific evidence chunks from Qdrant
    retrieved_evidence: list[EvidenceChunk]

    # Pre-formatted citation string ready for prompt injection ([1] CITATION ID: ...)
    evidence_text: str | None

    # ── Guardrails & Control Flow ────────────────────────────────────────────
    # List of constraint violations detected by the guardrail validator
    validation_errors: list[str]

    # Guardrail pass/fail status
    is_valid: bool

    # Loop iteration counter to prevent infinite refinement loops
    iteration_count: int
