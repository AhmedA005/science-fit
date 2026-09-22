"""
LLM Configuration and Factory for Science-Fit.

Initializes the ChatOllama model with credentials, host configuration,
and parameters aligned with the project's evidence-based constraints.
"""

from typing import Any
from langchain_ollama import ChatOllama

from src.config import Config

def get_llm(
    temperature: float = 0.2,
    model_name: str | None = None,
    **kwargs: Any,
) -> ChatOllama:
    """
    Factory function returning a configured ChatOllama instance.

    Args:
        temperature: Low temperature (default 0.2) recommended for evidence-based
                     fidelity and adherence to pre-calculated numerical context.
        model_name: Optional override for the model (defaults to Config.OLLAMA_LLM_MODEL).
        kwargs: Additional arguments passed to ChatOllama.

    Returns:
        ChatOllama instance ready for invocation or binding to tools/structured output.
    """
    selected_model = model_name or Config.OLLAMA_LLM_MODEL or "gemma4"
    
    client_kwargs: dict[str, Any] = {}
    if Config.OLLAMA_API_KEY:
        client_kwargs["headers"] = Config.OLLAMA_AUTH_HEADERS

    return ChatOllama(
        model=selected_model,
        base_url=Config.OLLAMA_HOST,
        temperature=temperature,
        client_kwargs=client_kwargs,
        async_client_kwargs=client_kwargs,
        validate_model_on_init=False,
        **kwargs,
    )


# Default shared LLM instance for coaching and synthesis
coach_llm = get_llm(temperature=0.2)

# Strict LLM instance with 0.0 temperature for routing and guardrails
strict_llm = get_llm(temperature=0.0)
