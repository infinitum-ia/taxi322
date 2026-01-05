"""Dependency injection for FastAPI."""

from functools import lru_cache

from app.services.graph_service import GraphService


@lru_cache()
def get_graph_service() -> GraphService:
    """
    Get the graph service instance (singleton).

    Returns:
        GraphService instance
    """
    return GraphService()
