"""
LangGraph Nodes for Science-Fit.

This file contains the node functions for the LangGraph workflow.
Each node receives the current `FitnessAgentState` and returns a dictionary
containing only the keys it wants to update.

Follow the TODOs below to implement the agent logic!
"""

import logging
import re
from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agent.llm import coach_llm, strict_llm
from src.agent.prompts import (
    INTENT_ROUTER_SYSTEM_PROMPT,
    build_coach_system_message,
)
from src.agent.state import FitnessAgentState
from src.database import AsyncSessionLocal
from src.rag.retriever import evidence_retriever
from src.services.training_engine import TrainingEngine

logger = logging.getLogger(__name__)


async def load_user_context_node(state: FitnessAgentState) -> Dict[str, Any]:
    """
    Node 1: Deterministic Context Injection.

    Checks if the user context is already loaded in the state.
    If not, it queries PostgreSQL via the TrainingEngine and injects:
      - user_context
      - workout_context
      - nutrition_targets
      - engine_context_text

    LangGraph Rule: Nodes return a dict of keys to update in the state.
    """
    # If already loaded in a previous turn of the same thread, skip DB query
    if state.get("engine_context_text"):
        return {}

    user_id = state.get("user_id", 1)

    async with AsyncSessionLocal() as session:
        engine = TrainingEngine(session)
        ctx = await engine.build_context(user_id=user_id, weeks_of_history=4)
        context_text = engine.format_context_for_llm(ctx)

        return {
            "user_context": ctx.user,
            "workout_context": ctx.workout,
            "nutrition_targets": ctx.nutrition,
            "engine_context_text": context_text,
        }


async def route_intent_node(state: FitnessAgentState) -> Dict[str, Any]:
    """
    Node 2: Intent Classifier.

    Inspects the latest user message and classifies it into one of:
      - workout_review
      - workout_planning
      - nutrition_guidance
      - scientific_inquiry
      - general_chat

    Uses `strict_llm` (temperature 0.0) for deterministic classification.
    """
    messages = state.get("messages", [])
    if not messages:
        return {"intent": "general_chat"}

    # Find the latest human message
    last_user_msg = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage) or getattr(msg, "type", "") == "human":
            last_user_msg = str(msg.content)
            break

    if not last_user_msg:
        return {"intent": "general_chat"}

    prompt_messages = [
        SystemMessage(content=INTENT_ROUTER_SYSTEM_PROMPT),
        HumanMessage(content=f"User query: {last_user_msg}"),
    ]
    response = await strict_llm.ainvoke(prompt_messages)
    classified_intent = response.content.strip().lower()

    valid_intents = {
        "workout_review",
        "workout_planning",
        "nutrition_guidance",
        "scientific_inquiry",
        "general_chat",
    }
    if classified_intent not in valid_intents:
        classified_intent = "workout_review"

    return {"intent": classified_intent}


async def retrieve_evidence_node(state: FitnessAgentState) -> Dict[str, Any]:
    """
    Node 3: Scientific Evidence RAG.

    Searches Qdrant for peer-reviewed literature matching the user query
    and formats standardized citation tags ([MORTON-2018], [SCHOENFELD-2021]).
    """
    intent = state.get("intent", "general_chat")

    # If general chat, no evidence needed
    if intent == "general_chat":
        return {"retrieved_evidence": [], "evidence_text": ""}

    messages = state.get("messages", [])
    query = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage) or getattr(msg, "type", "") == "human":
            query = str(msg.content)
            break

    # Determine RAG category filter based on intent
    category = "nutrition" if intent == "nutrition_guidance" else "training"

    chunks = evidence_retriever.search(query=query, top_k=3, category=category)
    evidence_text = evidence_retriever.format_evidence_for_prompt(chunks)

    return {
        "retrieved_evidence": chunks,
        "evidence_text": evidence_text,
    }


async def coach_node(state: FitnessAgentState) -> Dict[str, Any]:
    """
    Node 4: LLM Coach Response Generation.

    Assembles the dynamic system prompt with:
      - Ground-truth Layer 3 user context
      - RAG scientific evidence citations
      - Any guardrail validation errors from a prior pass
    Invokes `coach_llm` and appends an AIMessage to the conversation.
    """
    engine_context_text = state.get("engine_context_text")
    evidence_text = state.get("evidence_text")
    validation_errors = state.get("validation_errors", [])
    messages = list(state.get("messages", []))


    sys_content = build_coach_system_message(
        engine_context_text=engine_context_text,
        evidence_text=evidence_text,
        validation_errors=validation_errors,
    )

    llm_payload = [SystemMessage(content=sys_content)] + messages
    response = await coach_llm.ainvoke(llm_payload)

    return {
        "messages": [response],
    }


async def guardrail_validator_node(state: FitnessAgentState) -> Dict[str, Any]:
    """
    Node 5: Scientific Guardrail Validator.

    Analyzes the latest coach AIMessage for safety violations:
      - Did the coach recommend a crash diet / dangerous deficit (>1000 kcal)?
      - Did the coach prescribe volume that exceeds the user's MRV?

    Returns:
      is_valid: True if passed, False if violated
      validation_errors: list of violation descriptions
      iteration_count: incremented by 1
    """
    messages = state.get("messages", [])
    iteration = state.get("iteration_count", 0) + 1
    errors: list[str] = []

    last_ai_msg = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) or getattr(msg, "type", "") == "ai":
            last_ai_msg = str(msg.content).lower()
            break

    # 1. Calorie Deficit Guardrail: Catch numerical deficits > 1000 kcal
    # Matches patterns like "deficit of 1200", "1200 kcal deficit", "1500 calorie deficit"
    deficit_match = re.search(
        r"(?:deficit\s*(?:of)?\s*(\d{3,4}))|(?:(\d{3,4})\s*(?:kcal|calorie|cal)?\s*deficit)",
        last_ai_msg,
    )
    if deficit_match:
        deficit_val = int(deficit_match.group(1) or deficit_match.group(2))
        if deficit_val > 1000:
            errors.append(
                f"Unsafe calorie deficit suggested ({deficit_val} kcal/day). "
                "Evidence-based guidelines (ISSN, Helms 2014) recommend a maximum deficit "
                "of 500-750 kcal/day to prevent muscle loss and metabolic slowdown."
            )

    # 2. Volume Landmark Guardrail: Check for excessive weekly sets per muscle (> 25 sets)
    # Matches patterns like "30 sets per week", "28 sets/week", "32 weekly sets"
    volume_match = re.search(
        r"(\d{2})\s*(?:sets?\s*(?:per|/)\s*week|weekly\s*sets?)",
        last_ai_msg,
    )
    if volume_match:
        sets_val = int(volume_match.group(1))
        if sets_val > 25:
            errors.append(
                f"Excessive training volume suggested ({sets_val} sets/week). "
                "Schoenfeld (2017) and ACSM guidelines indicate Maximum Recoverable Volume "
                "(MRV) rarely exceeds 20-25 sets/week for any single muscle group."
            )

    is_valid = len(errors) == 0 or iteration >= 2

    return {
        "is_valid": is_valid,
        "validation_errors": errors,
        "iteration_count": iteration,
    }
