"""Token tracking service for phone conversations."""

from typing import Optional
from pathlib import Path
import logging
import os

logger = logging.getLogger(__name__)

# Get base directory (project root)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Create logs directory if it doesn't exist
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Token usage file in logs directory
TOKEN_FILE = LOGS_DIR / "token_usage.txt"

logger.info(f"📊 Token usage file will be saved to: {TOKEN_FILE}")


class TokenTracker:
    """Tracks token usage per phone conversation."""

    @staticmethod
    def extract_tokens_from_llm_response(result) -> dict[str, int]:
        """
        Extract tokens from LLM response metadata.

        Args:
            result: AIMessage from LLM invocation

        Returns:
            Dict with 'input' and 'output' token counts
        """
        # Try multiple ways to get token usage
        input_tokens = 0
        output_tokens = 0

        # Method 1: Check for usage_metadata (newer LangChain versions >= 0.2)
        if hasattr(result, "usage_metadata") and result.usage_metadata:
            usage = result.usage_metadata
            # In usage_metadata, keys are: input_tokens, output_tokens
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)

            if input_tokens > 0 or output_tokens > 0:
                logger.debug(f"✅ Extracted tokens from usage_metadata: input={input_tokens}, output={output_tokens}")
                return {"input": input_tokens, "output": output_tokens}

        # Method 2: Check for response_metadata (older LangChain versions)
        if hasattr(result, "response_metadata"):
            metadata = result.response_metadata
            logger.debug(f"🔍 DEBUG - Found response_metadata: {metadata}")

            token_usage = metadata.get("token_usage", {})
            logger.debug(f"🔍 DEBUG - token_usage dict: {token_usage}")

            if token_usage:
                input_tokens = token_usage.get("prompt_tokens", 0)
                output_tokens = token_usage.get("completion_tokens", 0)
                logger.info(f"✅ Extracted tokens from response_metadata: input={input_tokens}, output={output_tokens}")
                return {"input": input_tokens, "output": output_tokens}

        # Method 3: Check if it's a dict with usage key (some integrations)
        if isinstance(result, dict) and "usage" in result:
            usage = result["usage"]
            logger.debug(f"🔍 DEBUG - Found usage in dict: {usage}")
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            logger.info(f"✅ Extracted tokens from dict usage: input={input_tokens}, output={output_tokens}")
            return {"input": input_tokens, "output": output_tokens}

        logger.warning(f"⚠️ Could not find token usage in result. Full result: {result}")
        return {"input": 0, "output": 0}

    @staticmethod
    def is_farewell_message(message: str) -> bool:
        """
        Detect if message is a farewell/goodbye.

        Args:
            message: User message to analyze

        Returns:
            True if message contains farewell keywords
        """
        if not message:
            return False

        message_lower = message.lower()
        farewell_keywords = [
            "gracias", "adiós", "adios", "chao", "chau",
            "hasta luego", "nos vemos", "bye", "muchas gracias"
        ]

        return any(keyword in message_lower for keyword in farewell_keywords)

    @staticmethod
    def write_session_to_file(
        client_id: str,
        duration: float,
        input_tokens: int,
        output_tokens: int
    ):
        """
        Append session data to token_usage.txt.

        Format: client_id | duration | input_tokens | output_tokens

        Args:
            client_id: Phone number or client identifier
            duration: Session duration in seconds
            input_tokens: Total input tokens consumed
            output_tokens: Total output tokens generated
        """
        try:
            # Append mode is thread-safe for concurrent writes
            with open(TOKEN_FILE, "a", encoding="utf-8") as f:
                line = f"{client_id} | {duration:.2f} | {input_tokens} | {output_tokens}\n"
                f.write(line)

            logger.info(f"📊 Token tracking saved: {client_id} ({duration:.2f}s)")

        except IOError as e:
            # Don't raise - we don't want to break the conversation
            logger.error(f"❌ Error writing token tracking: {e}")
