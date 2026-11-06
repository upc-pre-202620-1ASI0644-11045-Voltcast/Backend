import asyncio
import json

import pytest
from aiohttp import ClientResponseError, web
from aiohttp.test_utils import TestServer
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from shared.infrastructure.push import fcm_client


def service_account() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    return json.dumps({"project_id": "voltcast-test", "client_email": "svc@voltcast-test.iam", "private_key": pem})


async def fake_google(handler_for_fcm):
    app = web.Application()

    async def token(request):
        form = await request.post()
        assert form["grant_type"].endswith("jwt-bearer") and form["assertion"]
        return web.json_response({"access_token": "abc", "expires_in": 3600})

    app.router.add_post("/token", token)
    app.router.add_post("/fcm/{project}", handler_for_fcm)
    server = TestServer(app)
    await server.start_server()
    return server


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("FIREBASE_CREDENTIALS_JSON", service_account())
    monkeypatch.setitem(fcm_client._access, "token", "")


def run_against(monkeypatch, handler, tokens):
    async def scenario():
        server = await fake_google(handler)
        try:
            base = f"http://127.0.0.1:{server.port}"
            monkeypatch.setattr(fcm_client, "TOKEN_URL", f"{base}/token")
            monkeypatch.setattr(fcm_client, "FCM_URL", base + "/fcm/{project}")
            return await fcm_client.send_push(tokens, "Title", "Body", {"notification_id": "7"})
        finally:
            await server.close()

    return asyncio.run(scenario())


def test_returns_the_tokens_fcm_does_not_know_and_sends_the_message(configured, monkeypatch):
    seen = []

    async def fcm(request):
        assert request.match_info["project"] == "voltcast-test"
        assert request.headers["Authorization"] == "Bearer abc"
        message = (await request.json())["message"]
        seen.append(message)
        if message["token"] == "gone":
            return web.json_response({"error": {"status": "NOT_FOUND"}}, status=404)
        if message["token"] == "bad":
            return web.json_response({"error": {"message": "The registration token is not a valid FCM registration token"}}, status=400)
        return web.json_response({"name": "ok"})

    assert run_against(monkeypatch, fcm, ["good", "gone", "bad"]) == ["gone", "bad"]
    assert seen[0] == {"token": "good", "notification": {"title": "Title", "body": "Body"}, "data": {"notification_id": "7"}}


def test_any_other_error_is_raised_so_the_notification_is_retried(configured, monkeypatch):
    async def fcm(request):
        return web.Response(status=500)

    with pytest.raises(ClientResponseError):
        run_against(monkeypatch, fcm, ["good"])


def test_says_so_when_firebase_is_not_configured(monkeypatch):
    monkeypatch.delenv("FIREBASE_CREDENTIALS_JSON", raising=False)
    with pytest.raises(fcm_client.PushNotConfigured):
        asyncio.run(fcm_client.send_push(["good"], "Title", "Body", {}))
