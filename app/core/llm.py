"""LLM client factory for ChatOpenAI."""

from langchain_openai import ChatOpenAI
from app.core.config import settings


def get_llm() -> ChatOpenAI:
    """
    Create and return a ChatOpenAI LLM instance.

    Returns:
        ChatOpenAI: Configured LLM client
    """
    return ChatOpenAI(
        api_key=settings.OPENAI_API_KEY,
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
    )
