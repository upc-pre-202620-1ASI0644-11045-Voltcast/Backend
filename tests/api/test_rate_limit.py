import fakeredis
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from tests.conftest import API, SUPERVISOR_EMAIL, SUPERVISOR_PASSWORD, login


@pytest.fixture
def fake_redis(monkeypatch):
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    monkeypatch.setattr("shared.infrastructure.security.rate_limiter.get_redis", lambda: redis)
    return redis


def bad_login(client, email="nobody@voltcast.com"):
    return client.post(f"{API}/auth/login", json={"email": email, "password": "Wrong#Pass1"})


def bad_logins_from_one_ip(client, count):
    """Every attempt uses another email, so only the per-IP limit can react."""
    return [bad_login(client, f"nobody{number}@voltcast.com") for number in range(count)]


def register(client, number):
    return client.post(
        f"{API}/auth/register",
        json={"full_name": "Test User", "email": f"user{number}@voltcast.com", "password": "Valid#Pass1"},
    )


def test_login_allows_25_attempts_per_minute_then_answers_429(client, fake_redis):
    statuses = [response.status_code for response in bad_logins_from_one_ip(client, 27)]
    assert statuses == [401] * 25 + [429] * 2


def test_blocked_requests_tell_when_to_retry(client, fake_redis):
    bad_logins_from_one_ip(client, 25)
    response = bad_login(client, "nobody99@voltcast.com")
    assert response.status_code == 429
    assert 0 < int(response.headers["Retry-After"]) <= 60
    assert "Too many requests" in response.json()["detail"]


def test_register_allows_5_requests_per_hour(client, fake_redis):
    statuses = [register(client, number).status_code for number in range(7)]
    assert statuses == [201] * 5 + [429] * 2


def test_every_endpoint_has_its_own_counter(client, fake_redis):
    bad_logins_from_one_ip(client, 26)
    assert bad_login(client, "nobody99@voltcast.com").status_code == 429
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
    assert {bad_login(client).status_code for _ in range(30)} == {401}


def test_the_limiter_is_skipped_when_redis_is_not_configured(client):
    assert {bad_login(client).status_code for _ in range(12)} == {401}


def test_an_email_is_blocked_after_5_failed_logins_whatever_the_ip_limit(client, fake_redis):
    statuses = [bad_login(client).status_code for _ in range(7)]
    assert statuses == [401] * 5 + [429] * 2


def test_the_blocked_email_tells_when_to_retry(client, fake_redis):
    for _ in range(5):
        bad_login(client)
    response = bad_login(client)
    assert response.status_code == 429
    assert 0 < int(response.headers["Retry-After"]) <= 300
    assert "Too many requests" in response.json()["detail"]


def test_a_blocked_email_is_refused_even_with_the_right_password(client, fake_redis):
    for _ in range(5):
        bad_login(client, SUPERVISOR_EMAIL)
    assert login(client, SUPERVISOR_EMAIL, SUPERVISOR_PASSWORD).status_code == 429


def test_blocking_one_email_does_not_affect_another(client, fake_redis):
    for _ in range(6):
        bad_login(client, "victim@voltcast.com")
    assert bad_login(client, "other@voltcast.com").status_code == 401


def test_the_email_is_counted_without_regard_to_case_or_spaces(client, fake_redis):
    variants = ["Nobody@voltcast.com", "NOBODY@VOLTCAST.COM", "nobody@voltcast.com"] * 2
    assert [bad_login(client, email).status_code for email in variants] == [401] * 5 + [429]


def test_a_successful_login_resets_the_failed_attempts(client, fake_redis):
    for _ in range(4):
        bad_login(client, SUPERVISOR_EMAIL)
    assert login(client, SUPERVISOR_EMAIL, SUPERVISOR_PASSWORD).status_code == 200
    assert [bad_login(client, SUPERVISOR_EMAIL).status_code for _ in range(4)] == [401] * 4
