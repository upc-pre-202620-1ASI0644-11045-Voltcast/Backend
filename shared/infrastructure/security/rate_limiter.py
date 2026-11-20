import logging

from fastapi import HTTPException, Request
from redis.exceptions import RedisError

from shared.infrastructure.cache.redis_client import get_redis

logger = logging.getLogger(__name__)


def rate_limit(name: str, max_requests: int, window_seconds: int):
    """
    FastAPI dependency factory: limits the requests per client IP to `max_requests` every `window_seconds`
    (fixed window kept in Redis). Answers 429 with a Retry-After header when the limit is exceeded.

    The limiter is skipped when Redis is not configured or unavailable, so a cache outage never blocks
    the API.

    Usage:
        @router.post("/register", dependencies=[Depends(rate_limit("register", 5, 3600))])
    """

    async def dependency(request: Request) -> None:
        redis = get_redis()
        if redis is None:
            return

        client_ip = request.client.host if request.client else "unknown"
        key = f"ratelimit:{name}:{client_ip}"
        try:
            # One atomic transaction: create the counter with its expiry (only if absent), count and read the TTL
            pipeline = redis.pipeline(transaction=True)
            pipeline.set(key, 0, ex=window_seconds, nx=True)
            pipeline.incr(key)
            pipeline.ttl(key)
            _, count, ttl = await pipeline.execute()
        except RedisError as error:
            logger.warning("Rate limiter skipped, Redis unavailable: %s", error)
            return

        if count > max_requests:
            retry_after = max(int(ttl), 1)
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests. Try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency
