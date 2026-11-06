import json
import os
import time

import aiohttp
import jwt

SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
TOKEN_URL = "https://oauth2.googleapis.com/token"
FCM_URL = "https://fcm.googleapis.com/v1/projects/{project}/messages:send"

_access = {"token": "", "expires": 0.0}


class PushNotConfigured(Exception):
    pass


def _credentials() -> dict:
    """The Firebase service account (the JSON file, on one line) from FIREBASE_CREDENTIALS_JSON."""
    raw = os.getenv("FIREBASE_CREDENTIALS_JSON", "")
    if not raw:
        raise PushNotConfigured("FIREBASE_CREDENTIALS_JSON is not set")
    return json.loads(raw)


async def _access_token(session: aiohttp.ClientSession, credentials: dict) -> str:
    """OAuth token of the service account, kept until a minute before it expires."""
    now = time.time()
    if _access["token"] and _access["expires"] > now + 60:
        return _access["token"]
    assertion = jwt.encode(
        {"iss": credentials["client_email"], "scope": SCOPE, "aud": TOKEN_URL, "iat": int(now), "exp": int(now) + 3600},
        credentials["private_key"],
        algorithm="RS256",
    )
    async with session.post(
        TOKEN_URL, data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion}
    ) as response:
        response.raise_for_status()
        body = await response.json()
    _access.update(token=body["access_token"], expires=now + body["expires_in"])
    return _access["token"]


async def send_push(tokens: list[str], title: str, body: str, data: dict[str, str]) -> list[str]:
    """
    Sends the notification to every device token. Returns the tokens FCM no longer knows (uninstalled app or expired
    token), so the caller can forget them. Any other error is raised: the notification stays pending and is retried.
    """
    credentials = _credentials()
    invalid: list[str] = []
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {await _access_token(session, credentials)}"}
        url = FCM_URL.format(project=credentials["project_id"])
        for token in tokens:
            message = {"message": {"token": token, "notification": {"title": title, "body": body}, "data": data}}
            async with session.post(url, json=message, headers=headers) as response:
                if response.status == 404 or (response.status == 400 and "registration token" in (await response.text()).lower()):
                    invalid.append(token)
                else:
                    response.raise_for_status()
    return invalid
