import logging
import os

from dotenv import load_dotenv
from redis.asyncio import Redis, from_url

load_dotenv()

logger = logging.getLogger(__name__)

_client: Redis | None = None


def get_redis() -> Redis | None:
    """
    Shared Redis client (Azure Cache for Redis in production).
    Returns None when REDIS_URL is not configured, so the API still runs without Redis in local development.
    """
    global _client
    url = os.getenv("REDIS_URL")
    if not url:
        return None
    if _client is None:
        _client = from_url(url, decode_responses=True)
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
        logger.info("Redis connection closed")
