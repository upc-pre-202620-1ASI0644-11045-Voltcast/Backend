"""
The Azure Storage adapters, against the Azurite emulator (never a real account: it empties the task queues). Skipped
unless AZURE_STORAGE_TEST_CONNECTION_STRING is set to the emulator's connection string:
  azurite --silent --location <dir> --skipApiVersionCheck
"""
import asyncio
import os
from uuid import uuid4

import pytest
from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient
from azure.storage.queue import QueueServiceClient

from shared.infrastructure.queue.task_queue import AzureTaskQueue, ETL_QUEUE, TRAINING_QUEUE, get_task_queue
from shared.infrastructure.storage.file_storage import AzureBlobStorage, get_file_storage
from tests.api.test_etl import dataset, run_etl, uploaded

CONNECTION = os.getenv("AZURE_STORAGE_TEST_CONNECTION_STRING")
pytestmark = pytest.mark.skipif(not CONNECTION, reason="AZURE_STORAGE_TEST_CONNECTION_STRING is not set")


@pytest.fixture
def azure(monkeypatch):
    """A scratch container and empty task queues; the API and the worker pick them up from the environment."""
    container = f"test-{uuid4().hex[:12]}"
    BlobServiceClient.from_connection_string(CONNECTION).create_container(container)
    queues = QueueServiceClient.from_connection_string(CONNECTION)
    for name in (ETL_QUEUE, TRAINING_QUEUE):
        try:
            queues.create_queue(name)
        except ResourceExistsError:
            pass
        queues.get_queue_client(name).clear_messages()
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", CONNECTION)
    monkeypatch.setenv("AZURE_STORAGE_CONTAINER", container)
    yield container
    BlobServiceClient.from_connection_string(CONNECTION).delete_container(container)


class TestAzureBlobStorage:
    def test_saves_and_reads_back_the_same_bytes(self, azure):
        storage = AzureBlobStorage(CONNECTION, azure)
        assert asyncio.run(storage.save("raw/a.xlsx", b"\x00\x01data")) == "raw/a.xlsx"
        assert asyncio.run(storage.read("raw/a.xlsx")) == b"\x00\x01data"
        asyncio.run(storage.save("raw/a.xlsx", b"replaced"))
        assert asyncio.run(storage.read("raw/a.xlsx")) == b"replaced"

    def test_a_missing_file_raises_file_not_found(self, azure):
        with pytest.raises(FileNotFoundError):
            asyncio.run(AzureBlobStorage(CONNECTION, azure).read("processed/9/summary.json"))


class TestAzureTaskQueue:
    def test_messages_come_in_order_and_stay_hidden_until_deleted(self, azure):
        queue = AzureTaskQueue(CONNECTION)
        assert asyncio.run(queue.receive(ETL_QUEUE)) is None
        asyncio.run(queue.send(ETL_QUEUE, {"task": "etl", "dataset_id": 1}))
        asyncio.run(queue.send(ETL_QUEUE, {"task": "etl", "dataset_id": 2}))
        message, handle = asyncio.run(queue.receive(ETL_QUEUE))
        assert message == {"task": "etl", "dataset_id": 1}
        assert asyncio.run(queue.receive(ETL_QUEUE))[0] == {"task": "etl", "dataset_id": 2}  # the first one is being handled
        asyncio.run(queue.delete(handle))

    def test_the_environment_selects_the_azure_adapters(self, azure):
        assert isinstance(get_task_queue(), AzureTaskQueue) and isinstance(get_file_storage(), AzureBlobStorage)


class TestApiAndWorkerThroughAzure:
    def test_uploads_to_blob_and_queue_and_the_worker_cleans_it(self, client, engineer_headers, azure):
        dataset_id = uploaded(client, engineer_headers)
        assert run_etl(client) is True
        body = dataset(client, engineer_headers, dataset_id)
        assert body["upload_status"] == "ready" and body["summary"]["n_cells"] == 5
        assert run_etl(client) is False  # the message was deleted
