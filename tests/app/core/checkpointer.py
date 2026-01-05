"""Checkpointer factory for conversation persistence."""

from langgraph.checkpoint.memory import MemorySaver
from app.core.config import settings


def get_checkpointer():
    """
    Create and return a checkpointer based on configuration.

    Currently supports:
    - memory: InMemorySaver (development, no persistence)
    - postgres: PostgresSaver (production, requires PostgreSQL)
    - redis: RedisSaver (production, requires Redis)

    Returns:
        Checkpointer instance

    Raises:
        ValueError: If checkpointer type is not supported
    """
    if settings.CHECKPOINTER_TYPE == "memory":
        return MemorySaver()

    elif settings.CHECKPOINTER_TYPE == "postgres":
        # TODO: Implement PostgresSaver in Phase 7
        # from langgraph.checkpoint.postgres import PostgresSaver
        # return PostgresSaver.from_conn_string(settings.POSTGRES_CHECKPOINTER_URL)
        raise NotImplementedError("PostgresSaver not yet implemented. Use 'memory' for now.")

    elif settings.CHECKPOINTER_TYPE == "redis":
        # TODO: Implement RedisSaver in Phase 7
        # from langgraph.checkpoint.redis import RedisSaver
        # return RedisSaver.from_conn_info(
        #     host=settings.REDIS_HOST,
        #     port=settings.REDIS_PORT,
        #     db=settings.REDIS_DB
        # )
        raise NotImplementedError("RedisSaver not yet implemented. Use 'memory' for now.")

    else:
        raise ValueError(f"Unknown checkpointer type: {settings.CHECKPOINTER_TYPE}")
