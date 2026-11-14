from datetime import datetime, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from drive_integration.domain.model.aggregates.DriveConnection import DriveConnection, DriveFile
from shared.infrastructure.google import drive_client
from shared.infrastructure.persistence.configuration.database_configuration import AsyncSessionLocal
from shared.infrastructure.queue.task_queue import ETL_QUEUE, get_task_queue
from tests.api.test_datasets import DATASETS
from tests.api.test_dataset_merge import BASE, finish_training, ready_base
from tests.api.test_etl import dataset, run_etl
from tests.conftest import API
from tests.excel_files import section_rows, workbook_bytes
from worker.main import run

DRIVE = f"{API}/integrations/drive"
BASE_END = datetime(2026, 1, 30)  # the last day of BASE


def days(start: datetime, count: int) -> bytes:
    """A workbook of `count` days from `start`, with the same cells as BASE."""
    return workbook_bytes({"EL A": section_rows(days=count, cells=[1, 2], start=start), "EL B": section_rows(days=count, cells=[1], start=start)})


def after_base(offset: int, count: int) -> bytes:
    """`count` days that start `offset` days after the last day of BASE (1 = the next day)."""
    return days(BASE_END + timedelta(days=offset), count)


@pytest.fixture
def gdrive(monkeypatch) -> SimpleNamespace:
    """Replaces Google: `files` is the Drive folder (name -> bytes); set `invalid_grant` or `fail` to break the sync."""
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("GOOGLE_DRIVE_FOLDER_ID", "folder-id")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "https://backend.example.com/api/v1/integrations/drive/callback")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    fake = SimpleNamespace(files={}, modified={}, folder=True, invalid_grant=False, fail=False, refreshes=0)

    async def exchange_code(code):
        if code == "bad":
            raise ConnectionError("Google refused the code")
        return {"access_token": "access", "refresh_token": "refresh-secret"}

    async def account_email(access_token):
        return "empresa@gmail.com"

    async def refresh(refresh_token):
        fake.refreshes += 1
        if fake.invalid_grant:
            raise drive_client.InvalidGrant()
        return {"access_token": "access", "refresh_token": "rotated-refresh"}

    async def list_folder(access_token, folder):
        if fake.fail:
            raise ConnectionError("Drive is down")
        if not fake.folder:
            return None
        return [
            {"id": name, "name": name, "version": "v1", "size": len(content),
             "modified": fake.modified.get(name, "2020-01-01T00:00:00Z")}
            for name, content in fake.files.items()
        ]

    async def download(access_token, item_id):
        return fake.files[item_id]

    for function in (exchange_code, account_email, refresh, list_folder, download):
        monkeypatch.setattr(drive_client, function.__name__, function)
    return fake


def connect(client, headers) -> None:
    url = client.get(f"{DRIVE}/connect", headers=headers).json()["authorizationUrl"]
    state = parse_qs(urlparse(url).query)["state"][0]
    assert client.get(f"{DRIVE}/callback", params={"code": "good", "state": state}).status_code == 200


def sync(client) -> None:
    client.portal.call(run, "drive")


def status(client, headers) -> dict:
    return client.get(f"{DRIVE}/status", headers=headers).json()


def datasets(client, headers) -> list[dict]:
    return client.get(DATASETS, headers=headers).json()


def files(client) -> dict[str, tuple[str, str | None]]:
    async def read(session):
        return {f.name: (f.status, f.reason) for f in (await session.execute(select(DriveFile))).scalars()}

    async def run_query():
        async with AsyncSessionLocal() as session:
            return await read(session)

    return client.portal.call(run_query)


class TestConnect:
    def test_the_supervisor_gets_the_google_consent_page(self, client, gdrive, supervisor_headers):
        response = client.get(f"{DRIVE}/connect", headers=supervisor_headers)
        assert response.status_code == 200
        url = urlparse(response.json()["authorizationUrl"])
        query = parse_qs(url.query)
        assert (url.scheme, url.netloc, url.path) == ("https", "accounts.google.com", "/o/oauth2/v2/auth")
        assert query["scope"] == ["https://www.googleapis.com/auth/drive.readonly"] and query["client_id"] == ["client-id"]
        assert (query["access_type"], query["prompt"]) == (["offline"], ["consent"])
        assert len(query["state"][0]) >= 32

    def test_only_the_supervisor_connects_or_disconnects(self, client, gdrive, engineer_headers):
        assert client.get(f"{DRIVE}/connect", headers=engineer_headers).status_code == 403
        assert client.delete(DRIVE, headers=engineer_headers).status_code == 403
        assert client.get(f"{DRIVE}/connect").status_code in (401, 403)

    def test_without_the_azure_settings_it_says_so(self, client, supervisor_headers, monkeypatch):
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        response = client.get(f"{DRIVE}/connect", headers=supervisor_headers)
        assert (response.status_code, response.json()["detail"]) == (503, "Drive integration is not configured")

    def test_the_redirect_has_to_be_https(self, client, gdrive, supervisor_headers, monkeypatch):
        monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://backend.example.com/callback")
        assert client.get(f"{DRIVE}/connect", headers=supervisor_headers).status_code == 503
        monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/callback")
        assert client.get(f"{DRIVE}/connect", headers=supervisor_headers).status_code == 200

    def test_the_callback_stores_the_connection_with_the_token_encrypted(self, client, gdrive, supervisor_headers):
        connect(client, supervisor_headers)
        assert status(client, supervisor_headers)["account"] == "empresa@gmail.com"

        async def stored():
            async with AsyncSessionLocal() as session:
                return (await session.get(DriveConnection, 1)).refresh_token

        assert "refresh-secret" not in client.portal.call(stored)

    def test_the_state_works_once(self, client, gdrive, supervisor_headers):
        url = client.get(f"{DRIVE}/connect", headers=supervisor_headers).json()["authorizationUrl"]
        state = parse_qs(urlparse(url).query)["state"][0]
        assert client.get(f"{DRIVE}/callback", params={"code": "good", "state": state}).status_code == 200
        reused = client.get(f"{DRIVE}/callback", params={"code": "good", "state": state})
        assert reused.status_code == 400

    def test_failures_show_a_generic_page(self, client, gdrive, supervisor_headers):
        for params in ({"code": "good", "state": "invented"}, {"error": "access_denied", "state": "x"}, {}):
            page = client.get(f"{DRIVE}/callback", params=params)
            assert page.status_code == 400 and "No se pudo completar la conexión" in page.text
            assert "invented" not in page.text and "access_denied" not in page.text
        url = client.get(f"{DRIVE}/connect", headers=supervisor_headers).json()["authorizationUrl"]
        state = parse_qs(urlparse(url).query)["state"][0]
        refused = client.get(f"{DRIVE}/callback", params={"code": "bad", "state": state})
        assert refused.status_code == 400 and "Google" not in refused.text
        assert status(client, supervisor_headers)["connected"] is False

    def test_the_access_log_does_not_print_the_authorization_code(self):
        import logging

        from main import HideOAuthParams

        path = f"{DRIVE}/callback?state=abc123&iss=https://accounts.google.com&code=4/0AXYZsecret&scope=drive.readonly"
        record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d', ("1.2.3.4:1", "GET", path, "1.1", 200), None)
        HideOAuthParams().filter(record)
        line = record.getMessage()
        assert "4/0AXYZsecret" not in line and "abc123" not in line
        assert "code=***" in line and "state=***" in line and "scope=drive.readonly" in line

    def test_a_demoted_supervisor_cannot_finish_the_connection(self, client, gdrive, supervisor_headers):
        url = client.get(f"{DRIVE}/connect", headers=supervisor_headers).json()["authorizationUrl"]
        state = parse_qs(urlparse(url).query)["state"][0]

        async def disable():
            from sqlalchemy import update
            from iam.domain.model.aggregates.User import User, UserStatus
            async with AsyncSessionLocal() as session:
                await session.execute(update(User).values(status=UserStatus.DISABLED))
                await session.commit()

        client.portal.call(disable)
        assert client.get(f"{DRIVE}/callback", params={"code": "good", "state": state}).status_code == 400

    def test_connecting_again_replaces_the_connection(self, client, gdrive, supervisor_headers):
        connect(client, supervisor_headers)
        connect(client, supervisor_headers)
        assert status(client, supervisor_headers)["connected"] is True


class TestStatus:
    def test_without_a_connection(self, client, engineer_headers):
        assert status(client, engineer_headers) == {"connected": False, "account": None, "lastSyncAt": None, "error": None, "connectedAt": None}

    def test_every_user_reads_it(self, client, gdrive, supervisor_headers, engineer_headers):
        connect(client, supervisor_headers)
        body = status(client, engineer_headers)
        assert (body["connected"], body["account"], body["error"], body["lastSyncAt"]) == (True, "empresa@gmail.com", None, None)
        assert body["connectedAt"].endswith("Z") or "+00:00" in body["connectedAt"]
        assert client.get(f"{DRIVE}/status").status_code in (401, 403)

    def test_disconnecting_deletes_the_connection_and_keeps_the_datasets(self, client, gdrive, supervisor_headers):
        ready_base(client, supervisor_headers)
        connect(client, supervisor_headers)
        assert client.delete(DRIVE, headers=supervisor_headers).status_code == 204
        assert client.delete(DRIVE, headers=supervisor_headers).status_code == 204
        assert status(client, supervisor_headers)["connected"] is False
        assert len(datasets(client, supervisor_headers)) == 1


class TestSyncErrors:
    def test_nothing_happens_without_a_connection(self, client, gdrive):
        gdrive.files["a.xlsx"] = after_base(1, 5)
        sync(client)
        assert gdrive.refreshes == 0

    def test_invalid_grant_stops_the_sync_and_is_not_retried(self, client, gdrive, supervisor_headers):
        connect(client, supervisor_headers)
        gdrive.invalid_grant = True
        sync(client)
        assert status(client, supervisor_headers)["error"] == "invalid_grant"
        sync(client)
        assert gdrive.refreshes == 1  # the second run did not even ask Google
        connect(client, supervisor_headers)  # connecting again clears it
        assert status(client, supervisor_headers)["error"] is None

    def test_a_failed_run_keeps_the_last_success_and_is_retried(self, client, gdrive, supervisor_headers):
        connect(client, supervisor_headers)
        sync(client)
        done = status(client, supervisor_headers)["lastSyncAt"]
        assert done is not None
        gdrive.fail = True
        sync(client)
        failed = status(client, supervisor_headers)
        assert (failed["error"], failed["lastSyncAt"]) == ("sync_failed", done)
        gdrive.fail = False
        sync(client)
        assert status(client, supervisor_headers)["error"] is None

    def test_a_missing_folder_fails_the_run_and_keeps_the_last_success(self, client, gdrive, supervisor_headers):
        connect(client, supervisor_headers)
        sync(client)
        done = status(client, supervisor_headers)["lastSyncAt"]
        gdrive.folder = False
        sync(client)
        failed = status(client, supervisor_headers)
        assert (failed["error"], failed["lastSyncAt"]) == ("sync_failed", done)
        gdrive.folder = True  # the folder is back: the next run clears the error
        sync(client)
        assert status(client, supervisor_headers)["error"] is None

    def test_the_rotated_refresh_token_is_kept(self, client, gdrive, supervisor_headers, monkeypatch):
        connect(client, supervisor_headers)
        used = []
        original = drive_client.refresh

        async def spy(refresh_token):
            used.append(refresh_token)
            return await original(refresh_token)

        monkeypatch.setattr(drive_client, "refresh", spy)
        sync(client)
        sync(client)
        assert used == ["refresh-secret", "rotated-refresh"]


class TestSyncDatasets:
    def test_the_first_files_become_the_first_dataset_once_they_can_be_trained_on(self, client, gdrive, supervisor_headers):
        connect(client, supervisor_headers)
        gdrive.files["part1.xlsx"] = days(datetime(2026, 1, 1), 6)  # the tests train with 10 days
        sync(client)
        assert datasets(client, supervisor_headers) == []
        gdrive.files["part2.xlsx"] = days(datetime(2026, 1, 7), 6)
        sync(client)
        [created] = datasets(client, supervisor_headers)
        assert created["base_dataset_id"] is None
        run_etl(client)
        ready = dataset(client, supervisor_headers, created["id"])
        assert (ready["upload_status"], ready["summary"]["days"]) == ("ready", 12)

    def test_a_week_of_new_records_is_not_enough_to_retrain(self, client, gdrive, supervisor_headers):
        ready_base(client, supervisor_headers)
        connect(client, supervisor_headers)
        gdrive.files["w1.xlsx"] = after_base(1, 7)
        gdrive.files["w2.xlsx"] = after_base(8, 7)
        sync(client)
        assert len(datasets(client, supervisor_headers)) == 1
        assert {name: state for name, (state, _) in files(client).items()} == {"w1.xlsx": "pending", "w2.xlsx": "pending"}
        assert get_task_queue().pending(ETL_QUEUE) == []
        assert status(client, supervisor_headers)["error"] is None

    def test_thirty_new_days_make_one_dataset_that_complements_the_last_one_and_trains(self, client, gdrive, supervisor_headers):
        base_id = ready_base(client, supervisor_headers)
        connect(client, supervisor_headers)
        for week, offset in enumerate((1, 11, 21)):
            gdrive.files[f"w{week}.xlsx"] = after_base(offset, 10)
        sync(client)
        [created] = [d for d in datasets(client, supervisor_headers) if d["id"] != base_id]
        assert created["base_dataset_id"] == base_id
        assert {state for state, _ in files(client).values()} == {"consumed"}
        run_etl(client)  # no confirmation: it goes from raw to ready by itself
        merged = dataset(client, supervisor_headers, created["id"])
        assert merged["upload_status"] == "ready" and merged["summary"]["days"] == 60
        running = client.get(f"{API}/trainings", headers=supervisor_headers).json()
        assert [r["dataset_id"] for r in running if r["status"] == "running"] == [created["id"]]
        sync(client)  # nothing new: no second dataset
        assert len(datasets(client, supervisor_headers)) == 2

    def test_a_file_with_the_whole_history_works_too(self, client, gdrive, supervisor_headers):
        base_id = ready_base(client, supervisor_headers)
        connect(client, supervisor_headers)
        gdrive.files["history.xlsx"] = days(datetime(2026, 1, 1), 65)  # the base and 35 days more
        sync(client)
        [created] = [d for d in datasets(client, supervisor_headers) if d["id"] != base_id]
        run_etl(client)
        assert dataset(client, supervisor_headers, created["id"])["summary"]["days"] == 65

    def test_a_file_without_new_days_is_not_taken_into_account(self, client, gdrive, supervisor_headers):
        ready_base(client, supervisor_headers)
        connect(client, supervisor_headers)
        gdrive.files["old.xlsx"] = days(datetime(2026, 1, 1), 30)  # the same days the dataset already has
        gdrive.files["notes.xlsx"] = b"not a workbook"
        gdrive.files["readme.txt"] = b"ignored"
        sync(client)
        found = files(client)
        assert set(found) == {"old.xlsx", "notes.xlsx"}
        assert found["old.xlsx"][0] == "rejected" and "adds no days" in found["old.xlsx"][1]
        assert found["notes.xlsx"][0] == "rejected"
        assert len(datasets(client, supervisor_headers)) == 1 and status(client, supervisor_headers)["error"] is None

    def test_a_file_is_looked_at_once_per_version(self, client, gdrive, supervisor_headers, monkeypatch):
        ready_base(client, supervisor_headers)
        connect(client, supervisor_headers)
        gdrive.files["w1.xlsx"] = after_base(1, 7)
        downloads = []
        original = drive_client.download

        async def counting(access_token, item_id):
            downloads.append(item_id)
            return await original(access_token, item_id)

        monkeypatch.setattr(drive_client, "download", counting)
        sync(client)
        sync(client)
        assert downloads == ["w1.xlsx"]

    def test_a_file_still_being_uploaded_waits(self, client, gdrive, supervisor_headers):
        ready_base(client, supervisor_headers)
        connect(client, supervisor_headers)
        gdrive.files["w1.xlsx"] = after_base(1, 7)
        gdrive.modified["w1.xlsx"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        sync(client)
        assert files(client) == {}

    def test_a_gap_holds_the_file_until_the_days_in_between_arrive(self, client, gdrive, supervisor_headers):
        ready_base(client, supervisor_headers)
        connect(client, supervisor_headers)
        gdrive.files["late.xlsx"] = after_base(30, 10)  # 29 days missing; at most 12 are bridged
        sync(client)
        state, reason = files(client)["late.xlsx"]
        assert state == "held" and "without records" in reason
        gdrive.files["middle.xlsx"] = after_base(1, 28)
        sync(client)
        assert {name: state for name, (state, _) in files(client).items()} == {"late.xlsx": "consumed", "middle.xlsx": "consumed"}
        assert files(client)["late.xlsx"][1] is None  # the gap that held it is not shown once it is gone
        assert len(datasets(client, supervisor_headers)) == 2

    def test_while_a_training_runs_the_files_wait_for_the_next_run(self, client, gdrive, supervisor_headers):
        ready_base(client, supervisor_headers)  # its training counts as done
        connect(client, supervisor_headers)
        gdrive.files["month.xlsx"] = after_base(1, 35)

        async def start_training():
            from voltage_forecasting.domain.model.aggregates.TrainingExecution import TrainingExecution, TrainingStatus
            async with AsyncSessionLocal() as session:
                running = (await session.execute(select(TrainingExecution))).scalars().first()
                running.status = TrainingStatus.RUNNING
                await session.commit()

        client.portal.call(start_training)
        sync(client)
        assert len(datasets(client, supervisor_headers)) == 1
        assert files(client)["month.xlsx"][0] == "pending" and status(client, supervisor_headers)["error"] is None
        client.portal.call(finish_training, client)
        sync(client)
        assert len(datasets(client, supervisor_headers)) == 2


class Reply:
    """What aiohttp returns for a request, enough for the client."""

    def __init__(self, body, status=200):
        self._body, self.status = body, status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *error):
        return False

    async def json(self):
        return self._body

    def raise_for_status(self):
        assert self.status < 400


class TestDriveClient:
    def run_list(self, monkeypatch, folder_reply, pages):
        import asyncio

        calls = []

        async def fake_get(session, path, access_token, **params):
            calls.append((path, params.get("pageToken")))
            return folder_reply if path.startswith("files/") else Reply(pages[len(calls) - 2])

        monkeypatch.setattr(drive_client, "_get", fake_get)
        return asyncio.run(drive_client.list_folder("token", "folder-id")), calls

    def test_lists_the_excel_files_of_all_the_pages_and_leaves_out_google_documents(self, monkeypatch):
        pages = [
            {"files": [{"id": "1", "name": "a.xlsx", "md5Checksum": "m1", "size": "2048", "modifiedTime": "2026-01-01T00:00:00.000Z"},
                       {"id": "2", "name": "Sheet", "modifiedTime": "2026-01-01T00:00:00.000Z"}], "nextPageToken": "next"},
            {"files": [{"id": "3", "name": "b.xlsx", "md5Checksum": "m3", "size": "10", "modifiedTime": "2026-01-02T00:00:00.000Z"}]},
        ]
        items, calls = self.run_list(monkeypatch, Reply({"id": "folder-id", "trashed": False}), pages)
        assert [(i["id"], i["name"], i["version"], i["size"]) for i in items] == [("1", "a.xlsx", "m1", 2048), ("3", "b.xlsx", "m3", 10)]
        assert calls == [("files/folder-id", None), ("files", None), ("files", "next")]

    def test_a_missing_or_trashed_folder_is_none(self, monkeypatch):
        assert self.run_list(monkeypatch, Reply({}, status=404), [])[0] is None
        assert self.run_list(monkeypatch, Reply({"id": "folder-id", "trashed": True}), [])[0] is None
