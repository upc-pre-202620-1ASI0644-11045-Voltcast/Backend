"""
Shared fixtures. The whole API runs against a throwaway SQLite database, so no MySQL, Redis or SMTP
server is needed to run the tests.

The environment is configured BEFORE the application is imported: the database engine and the JWT
service read it at import time (values already in the environment win over the developer's .env).
"""
import os
import tempfile
from pathlib import Path

_DB_FILE = Path(tempfile.mkdtemp(prefix="voltcast-tests-")) / "test.db"

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_DB_FILE.as_posix()}"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-the-automated-tests-only"
os.environ["REDIS_URL"] = ""  # the rate limiter is skipped unless a test enables it
os.environ["SEED_ADMIN_EMAIL"] = "supervisor@voltcast.com"
os.environ["SEED_ADMIN_PASSWORD"] = "Super#Pass1"
os.environ["SEED_ADMIN_NAME"] = "Test Supervisor"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from shared.infrastructure.persistence.configuration.database_configuration import Base, engine  # noqa: E402

API = "/api/v1"
SUPERVISOR_EMAIL = os.environ["SEED_ADMIN_EMAIL"]
SUPERVISOR_PASSWORD = os.environ["SEED_ADMIN_PASSWORD"]
ENGINEER_PASSWORD = "Engi#Pass1"


async def _reset_database() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    await main.seed_roles()
    await main.seed_supervisor()


@pytest.fixture
def client():
    """A client over an empty database that only contains the roles and the seeded supervisor."""
    with TestClient(main.app) as test_client:
        test_client.portal.call(_reset_database)
        yield test_client


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def login(client: TestClient, email: str, password: str):
    return client.post(f"{API}/auth/login", json={"email": email, "password": password})


@pytest.fixture
def sent_codes(monkeypatch) -> dict:
    """Replaces the SMTP call: the verification codes are collected here, indexed by email."""
    codes: dict[str, str] = {}

    async def fake_send(to: str, code: str) -> None:
        codes[to] = code

    monkeypatch.setattr(
        "iam.application.internal.commandservice.PasswordResetServiceImpl.send_verification_code", fake_send
    )
    return codes


@pytest.fixture
def supervisor_headers(client) -> dict:
    response = login(client, SUPERVISOR_EMAIL, SUPERVISOR_PASSWORD)
    assert response.status_code == 200, response.text
    return bearer(response.json()["access_token"])


@pytest.fixture
def register_engineer(client, supervisor_headers):
    """Factory: registers an engineer, approves the request and returns (user_id, auth headers)."""

    def _register(email: str = "engineer@voltcast.com", full_name: str = "Test Engineer"):
        response = client.post(
            f"{API}/auth/register",
            json={"full_name": full_name, "email": email, "password": ENGINEER_PASSWORD},
        )
        assert response.status_code == 201, response.text
        user_id = response.json()["id"]
        approval = client.patch(
            f"{API}/users/{user_id}/approval", headers=supervisor_headers, json={"decision": "approve"}
        )
        assert approval.status_code == 200, approval.text
        token = login(client, email, ENGINEER_PASSWORD).json()["access_token"]
        return user_id, bearer(token)

    return _register


@pytest.fixture
def engineer_headers(register_engineer) -> dict:
    """Authenticated headers of an approved engineer (the actor of the cell management stories)."""
    return register_engineer()[1]
