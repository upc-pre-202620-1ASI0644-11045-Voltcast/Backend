import os
from urllib.parse import quote, urlencode, urlparse

import aiohttp

LOGIN_URL = "https://login.microsoftonline.com"
GRAPH_URL = "https://graph.microsoft.com/v1.0"
SCOPES = "Files.Read offline_access User.Read"  # the least that reads the files and keeps the connection alive
TIMEOUT = aiohttp.ClientTimeout(total=300)


class NotConfigured(Exception):
    pass


class InvalidGrant(Exception):
    """Microsoft no longer accepts the refresh token (password change, revoked sessions, 90 days unused...): the account has to be connected again."""


def _setting(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        raise NotConfigured(f"{name} is not set")
    return value


def _redirect_uri() -> str:
    uri = _setting("MS_REDIRECT_URI")
    parsed = urlparse(uri)
    if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1")):
        raise NotConfigured("MS_REDIRECT_URI must be HTTPS (http only for localhost)")
    return uri


def authorization_url(state: str) -> str:
    query = urlencode({
        "client_id": _setting("MS_CLIENT_ID"), "response_type": "code", "redirect_uri": _redirect_uri(),
        "response_mode": "query", "scope": SCOPES, "state": state, "prompt": "select_account",
    })
    return f"{LOGIN_URL}/{_setting('MS_TENANT_ID')}/oauth2/v2.0/authorize?{query}"


async def _token(data: dict) -> dict:
    body = {"client_id": _setting("MS_CLIENT_ID"), "client_secret": _setting("MS_CLIENT_SECRET"), "scope": SCOPES, **data}
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        async with session.post(f"{LOGIN_URL}/{_setting('MS_TENANT_ID')}/oauth2/v2.0/token", data=body) as response:
            if response.status == 400 and (await response.json(content_type=None)).get("error") == "invalid_grant":
                raise InvalidGrant()
            response.raise_for_status()
            return await response.json()


async def exchange_code(code: str) -> dict:
    return await _token({"grant_type": "authorization_code", "code": code, "redirect_uri": _redirect_uri()})


async def refresh(refresh_token: str) -> dict:
    """New access token; Microsoft may also return a new refresh token, which replaces the old one."""
    return await _token({"grant_type": "refresh_token", "refresh_token": refresh_token})


async def _get(session: aiohttp.ClientSession, url: str, access_token: str) -> aiohttp.ClientResponse:
    return await session.get(url, headers={"Authorization": f"Bearer {access_token}"})


async def account_email(access_token: str) -> str:
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        async with await _get(session, f"{GRAPH_URL}/me", access_token) as response:
            response.raise_for_status()
            profile = await response.json()
    return profile.get("mail") or profile["userPrincipalName"]


async def list_folder(access_token: str, folder: str) -> list[dict] | None:
    """The items of the folder (not the content of its subfolders), or None when the folder does not exist."""
    url = f"{GRAPH_URL}/me/drive/root:{quote(folder, safe='/')}:/children?$top=200&$select=id,name,eTag,size,file,lastModifiedDateTime"
    items: list[dict] = []
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        while url:
            async with await _get(session, url, access_token) as response:
                if response.status == 404:
                    return None
                response.raise_for_status()
                page = await response.json()
            items += page["value"]
            url = page.get("@odata.nextLink")
    return items


async def download(access_token: str, item_id: str) -> bytes:
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        async with await _get(session, f"{GRAPH_URL}/me/drive/items/{quote(item_id)}/content", access_token) as response:
            response.raise_for_status()
            return await response.read()
