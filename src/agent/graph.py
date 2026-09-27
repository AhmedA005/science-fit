"""
LangGraph Workflow Definition for Science-Fit.

Builds and compiles the StateGraph connecting:
  START -> load_user_context -> route_intent -> (conditional: retrieve_evidence)
        -> coach -> guardrail_validator -> (conditional: loop back or END)

"""

from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from src.agent.nodes import (
    coach_node,
    guardrail_validator_node,
    load_user_context_node,
    retrieve_evidence_node,
    route_intent_node,
)
from src.agent.state import FitnessAgentState
from src.agent.tools import AGENT_TOOLS


def should_retrieve_evidence(state: FitnessAgentState) -> Literal["retrieve_evidence", "coach"]:
    """
    Conditional Edge Function 1.

    Decides whether to route through RAG evidence retrieval or go straight
    to the coach based on the classified intent.
    """
    intent = state.get("intent", "general_chat")
    if intent == "general_chat":
        return "coach"
    return "retrieve_evidence"


def check_guardrail_status(state: FitnessAgentState) -> Literal["coach", "__end__"]:
    """
    Conditional Edge Function 2 (Self-Correction Loop).

    Inspects guardrail validation results.
    If valid, proceeds to END.
    If invalid and under the loop limit, loops back to `coach` to self-correct!
    """
    is_valid = state.get("is_valid", True)
    iteration = state.get("iteration_count", 0)

    if not is_valid and iteration < 2:
        return "coach"
    return END


def build_agent_graph():
    """
    Assembles the StateGraph nodes and edges with tool execution and self-correction.
    """
    workflow = StateGraph(FitnessAgentState)

    # 1. Add nodes
    workflow.add_node("load_context", load_user_context_node)
    workflow.add_node("route_intent", route_intent_node)
    workflow.add_node("retrieve_evidence", retrieve_evidence_node)
    workflow.add_node("coach", coach_node)
    workflow.add_node("tools", ToolNode(AGENT_TOOLS))
    workflow.add_node("guardrail", guardrail_validator_node)

    # 2. Add edges
    workflow.add_edge(START, "load_context")
    workflow.add_edge("load_context", "route_intent")

    # 3. Conditional routing: whether to fetch initial RAG evidence
    workflow.add_conditional_edges(
        "route_intent",
        should_retrieve_evidence,
        {
            "retrieve_evidence": "retrieve_evidence",
            "coach": "coach",
        },
    )
    workflow.add_edge("retrieve_evidence", "coach")

    # 4. Conditional routing: tool execution or proceed to guardrail validation
    workflow.add_conditional_edges(
        "coach",
        tools_condition,
        {
            "tools": "tools",
            "__end__": "guardrail",
        },
    )
    workflow.add_edge("tools", "coach")

    # 5. Conditional routing: guardrail self-correction loop
    workflow.add_conditional_edges(
        "guardrail",
        check_guardrail_status,
        {
            "coach": "coach",
            END: END,
        },
    )

    # 6. Compile with in-memory checkpointer for multi-turn conversation
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


# Global compiled instance ready to invoke
fitness_agent_app = build_agent_graph()
