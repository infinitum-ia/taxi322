"""Token interceptor for agent nodes."""

from typing import Any
import time
from app.services.token_tracker import TokenTracker
import logging

logger = logging.getLogger(__name__)


def intercept_llm_call(result: Any, state: dict) -> dict:
    """
    Intercept LLM call and update token tracking in state.

    This function:
    1. Extracts tokens from LLM response
    2. Updates cumulative token counts
    3. Initializes start_time on first call

    Args:
        result: AIMessage from LLM
        state: Current TaxiState dictionary

    Returns:
        Updated state with token_tracking field
    """
    # Extract tokens from this invocation
    tokens = TokenTracker.extract_tokens_from_llm_response(result)

    logger.debug(f"📊 Tokens: input={tokens['input']}, output={tokens['output']}")

    # Initialize tracking structure if not present
    if "token_tracking" not in state or state.get("token_tracking") is None:
        state["token_tracking"] = {
            "start_time": time.time(),  # Unix timestamp
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "dispatch_executed": False,
            "tracking_saved": False  # Prevent duplicate saves
        }
        logger.debug(f"🆕 Initialized token tracking at {state['token_tracking']['start_time']}")

    # Accumulate tokens
    state["token_tracking"]["total_input_tokens"] += tokens["input"]
    state["token_tracking"]["total_output_tokens"] += tokens["output"]

    logger.debug(
        f"📈 Total tokens: "
        f"input={state['token_tracking']['total_input_tokens']}, "
        f"output={state['token_tracking']['total_output_tokens']}"
    )

    return state
