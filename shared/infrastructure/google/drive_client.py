import os
from urllib.parse import urlencode, urlparse

import aiohttp

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API_URL = "https://www.googleapis.com/drive/v3"
SCOPE = "https://www.googleapis.com/auth/drive.readonly"  # the least that lists and downloads the files of a folder
TIMEOUT = aiohttp.ClientTimeout(total=300)
FOLDER_MIME = "application/vnd.google-apps.folder"


class NotConfigured(Exception):
    pass


class InvalidGrant(Exception):
    """Google no longer accepts the refresh token (revoked access, password change, unused for 6 months...): the account has to be connected again."""


def _setting(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        raise NotConfigured(f"{name} is not set")
    return value


def _redirect_uri() -> str:
    uri = _setting("GOOGLE_REDIRECT_URI")
    parsed = urlparse(uri)
    if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1")):
        raise NotConfigured("GOOGLE_REDIRECT_URI must be HTTPS (http only for localhost)")
    return uri


def authorization_url(state: str) -> str:
    # prompt=consent makes Google return a refresh token every time, also when the account had already accepted.
    query = urlencode({
        "client_id": _setting("GOOGLE_CLIENT_ID"), "redirect_uri": _redirect_uri(), "response_type": "code",
        "scope": SCOPE, "access_type": "offline", "prompt": "consent", "state": state,
    })
    return f"{AUTH_URL}?{query}"


async def _token(data: dict) -> dict:
    body = {"client_id": _setting("GOOGLE_CLIENT_ID"), "client_secret": _setting("GOOGLE_CLIENT_SECRET"), **data}
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        async with session.post(TOKEN_URL, data=body) as response:
            if response.status == 400 and (await response.json(content_type=None)).get("error") == "invalid_grant":
                raise InvalidGrant()
            response.raise_for_status()
            return await response.json()


async def exchange_code(code: str) -> dict:
    return await _token({"grant_type": "authorization_code", "code": code, "redirect_uri": _redirect_uri()})


async def refresh(refresh_token: str) -> dict:
    """New access token. Google keeps the same refresh token, so the answer usually has none."""
    return await _token({"grant_type": "refresh_token", "refresh_token": refresh_token})


async def _get(session: aiohttp.ClientSession, path: str, access_token: str, **params) -> aiohttp.ClientResponse:
    return await session.get(f"{API_URL}/{path}", params=params, headers={"Authorization": f"Bearer {access_token}"})


async def account_email(access_token: str) -> str:
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        async with await _get(session, "about", access_token, fields="user(emailAddress)") as response:
            response.raise_for_status()
            return (await response.json())["user"]["emailAddress"]


def folder_id() -> str:
    """Drive has no paths: the folder where the Excel files are left is known by its id (the end of its URL)."""
    return _setting("GOOGLE_DRIVE_FOLDER_ID")


async def list_folder(access_token: str, folder: str) -> list[dict] | None:
    """
    The files of the folder, or None when it does not exist (or was trashed). Each one is {id, name, version, size,
    modified}, where `version` is its checksum: a new version of a file has another. Google Docs and Sheets are left
    out (they have no checksum and cannot be downloaded as they are): only files uploaded as Excel.
    """
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        async with await _get(session, f"files/{folder}", access_token, fields="id,trashed") as response:
            if response.status == 404:
                return None
            response.raise_for_status()
            if (await response.json())["trashed"]:
                return None
        items: list[dict] = []
        page_token = None
        while True:
            params = {
                "q": f"'{folder}' in parents and trashed = false and mimeType != '{FOLDER_MIME}'",
                "fields": "nextPageToken,files(id,name,md5Checksum,size,modifiedTime)", "pageSize": 200,
            }
            if page_token:
                params["pageToken"] = page_token
            async with await _get(session, "files", access_token, **params) as response:
                response.raise_for_status()
                page = await response.json()
            items += [
                {"id": f["id"], "name": f["name"], "version": f["md5Checksum"], "size": int(f.get("size", 0)), "modified": f["modifiedTime"]}
                for f in page["files"] if f.get("md5Checksum")
            ]
            page_token = page.get("nextPageToken")
            if not page_token:
                return items


async def download(access_token: str, item_id: str) -> bytes:
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        async with await _get(session, f"files/{item_id}", access_token, alt="media") as response:
            response.raise_for_status()
            return await response.read()
