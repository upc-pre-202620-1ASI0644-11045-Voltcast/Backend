import fakeredis
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from tests.conftest import API


@pytest.fixture
def fake_redis(monkeypatch):
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    monkeypatch.setattr("shared.infrastructure.security.rate_limiter.get_redis", lambda: redis)
    return redis


def bad_login(client):
    return client.post(f"{API}/auth/login", json={"email": "nobody@voltcast.com", "password": "Wrong#Pass1"})


def register(client, number):
    return client.post(
        f"{API}/auth/register",
        json={"full_name": "Test User", "email": f"user{number}@voltcast.com", "password": "Valid#Pass1"},
    )


def test_login_allows_10_attempts_per_minute_then_answers_429(client, fake_redis):
    statuses = [bad_login(client).status_code for _ in range(12)]
    assert statuses == [401] * 10 + [429] * 2


def test_blocked_requests_tell_when_to_retry(client, fake_redis):
    for _ in range(10):
        bad_login(client)
    response = bad_login(client)
    assert response.status_code == 429
    assert 0 < int(response.headers["Retry-After"]) <= 60
    assert "Too many requests" in response.json()["detail"]


def test_register_allows_5_requests_per_hour(client, fake_redis):
    statuses = [register(client, number).status_code for number in range(7)]
    assert statuses == [201] * 5 + [429] * 2


def test_every_endpoint_has_its_own_counter(client, fake_redis):
    for _ in range(11):
        bad_login(client)
    assert bad_login(client).status_code == 429
    assert register(client, 1).status_code == 201


def test_password_reset_request_is_limited_to_5_per_hour(client, fake_redis, sent_codes):
    statuses = [
        client.post(f"{API}/auth/password-reset/request", json={"email": "a@voltcast.com"}).status_code
        for _ in range(6)
    ]
    assert statuses == [200] * 5 + [429]


def test_the_limiter_never_blocks_the_api_when_redis_is_down(client, monkeypatch):
    class BrokenRedis:
        def pipeline(self, **kwargs):
            raise RedisConnectionError("redis is down")

    monkeypatch.setattr("shared.infrastructure.security.rate_limiter.get_redis", lambda: BrokenRedis())
    assert {bad_login(client).status_code for _ in range(12)} == {401}


def test_the_limiter_is_skipped_when_redis_is_not_configured(client):
    assert {bad_login(client).status_code for _ in range(12)} == {401}
