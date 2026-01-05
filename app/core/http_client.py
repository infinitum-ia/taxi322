"""Singleton HTTP client for connection pooling."""

import httpx
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache()
def get_http_client() -> httpx.AsyncClient:
    """
    Get a singleton HTTP client with connection pooling.

    This client reuses TCP/TLS connections across requests,
    significantly improving performance for repeated calls
    to the same hosts.

    Benefits:
    - Reuses TCP connections (no handshake overhead)
    - Reuses TLS sessions (no SSL/TLS negotiation)
    - Reduces latency by 50-80% for subsequent requests

    Returns:
        Configured AsyncClient with connection pooling
    """
    client = httpx.AsyncClient(
        timeout=10.0,
        limits=httpx.Limits(
            max_connections=100,  # Max connections total
            max_keepalive_connections=20,  # Keep 20 connections alive
            keepalive_expiry=30.0,  # Keep connections alive for 30s
        ),
        # Enable HTTP/2 for better performance (if backend supports it)
        http2=False,  # Set to True if backend supports HTTP/2
    )

    logger.info("🌐 HTTP client initialized with connection pooling")

    return client


async def close_http_client():
    """Close the HTTP client and cleanup connections."""
    try:
        client = get_http_client()
        await client.aclose()
        logger.info("🌐 HTTP client closed")
    except Exception as e:
        logger.error(f"Error closing HTTP client: {e}")
