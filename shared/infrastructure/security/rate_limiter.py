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
            raise _too_many_requests(ttl)

    return dependency


def _too_many_requests(ttl: int) -> HTTPException:
    # The client translates this exact detail, so keep the wording
    retry_after = max(int(ttl), 1)
    return HTTPException(
        status_code=429,
        detail=f"Too many requests. Try again in {retry_after} seconds.",
        headers={"Retry-After": str(retry_after)},
    )


class FailureLimiter:
    """
    Blocks an identifier (e.g. an email) after `max_failures` failed attempts within `window_seconds`
    (fixed window from the first failure, kept in Redis). Complements the per-IP `rate_limit`.
    Like it, it never blocks the API when Redis is not configured or unavailable.

    Call `check` before the attempt (raises 429), `record` after a failure and `clear` after a success.
    """

    def __init__(self, name: str, max_failures: int, window_seconds: int):
        self.name = name
        self.max_failures = max_failures
        self.window_seconds = window_seconds

    def _key(self, identifier: str) -> str:
        return f"ratelimit:{self.name}:{identifier.strip().lower()}"

    async def check(self, identifier: str) -> None:
        redis = get_redis()
        if redis is None:
            return
        key = self._key(identifier)
        try:
            pipeline = redis.pipeline(transaction=True)
            pipeline.get(key)
            pipeline.ttl(key)
            count, ttl = await pipeline.execute()
        except RedisError as error:
            logger.warning("Failure limiter skipped, Redis unavailable: %s", error)
            return
        if count is not None and int(count) >= self.max_failures:
            raise _too_many_requests(ttl)

    async def record(self, identifier: str) -> None:
        redis = get_redis()
        if redis is None:
            return
        key = self._key(identifier)
        try:
            pipeline = redis.pipeline(transaction=True)
            pipeline.set(key, 0, ex=self.window_seconds, nx=True)
            pipeline.incr(key)
            await pipeline.execute()
        except RedisError as error:
            logger.warning("Failure limiter skipped, Redis unavailable: %s", error)

    async def clear(self, identifier: str) -> None:
        redis = get_redis()
        if redis is None:
            return
        try:
            await redis.delete(self._key(identifier))
        except RedisError as error:
            logger.warning("Failure limiter skipped, Redis unavailable: %s", error)
