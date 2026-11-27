import asyncio

import fakeredis
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

import main

SECRET = "mysql-prod.internal:3306 password=hunter2"


class BrokenDatabase:
    def connect(self):
        raise OSError(SECRET)


class BrokenRedis:
    async def ping(self):
        raise RedisConnectionError(SECRET)


class HangingRedis:
    async def ping(self):
        await asyncio.sleep(60)


@pytest.fixture
def use_redis(monkeypatch):
    def _use(redis):
        monkeypatch.setenv("REDIS_URL", "redis://unused")
        monkeypatch.setattr("main.get_redis", lambda: redis)

    return _use


def test_everything_ok(client, use_redis):
    use_redis(fakeredis.FakeAsyncRedis())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "redis": "ok"}


def test_redis_not_configured(client):
    assert client.get("/health").json() == {"status": "ok", "database": "ok", "redis": "not_configured"}


@pytest.mark.parametrize("redis", [BrokenRedis(), HangingRedis()])
def test_redis_down_is_degraded_but_up(client, use_redis, monkeypatch, redis):
    monkeypatch.setattr(main, "HEALTH_TIMEOUT_SECONDS", 0.1)
    use_redis(redis)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "redis": "degraded"}
    assert "hunter2" not in response.text


def test_database_down_answers_503_and_only_logs_the_error(client, monkeypatch, caplog):
    monkeypatch.setattr(main, "engine", BrokenDatabase())
    response = client.get("/health")
    monkeypatch.undo()  # the shutdown of the app needs the real engine
    assert response.status_code == 503
    assert response.json() == {"status": "down", "database": "error", "redis": "not_configured"}
    assert "hunter2" in caplog.text


def test_a_hanging_database_answers_503(client, monkeypatch):
    async def hang():
        await asyncio.sleep(60)

    monkeypatch.setattr(main, "HEALTH_TIMEOUT_SECONDS", 0.1)
    monkeypatch.setattr(main, "_ping_database", hang)
    assert client.get("/health").status_code == 503


def test_head_works_for_uptime_monitors(client, monkeypatch):
    assert client.head("/health").status_code == 200
    monkeypatch.setattr(main, "engine", BrokenDatabase())
    assert client.head("/health").status_code == 503


def test_health_is_not_in_the_openapi_schema(client):
    assert "/health" not in client.get("/openapi.json").json()["paths"]
