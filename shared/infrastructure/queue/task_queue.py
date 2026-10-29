import asyncio
import json
import os
import time
from pathlib import Path
from uuid import uuid4

from azure.storage.queue.aio import QueueClient

# Azure Storage Queue names: lowercase letters, numbers and hyphens only.
ETL_QUEUE = "etl-tasks"
TRAINING_QUEUE = "training-tasks"


class LocalTaskQueue:
    """
    One JSON file per message in a folder shared by the API and the worker, so both can run as separate
    processes without Azure. A received message stays in the folder until it is deleted, so a worker that
    dies halfway finds it again (at-least-once, like an Azure Storage Queue).
    shortcut: a single worker, two workers could take the same message; use AZURE_STORAGE_CONNECTION_STRING in the cloud.
    """

    def __init__(self, root: Path):
        self._root = root

    async def send(self, queue: str, message: dict) -> None:
        def write() -> None:
            folder = self._root / queue
            folder.mkdir(parents=True, exist_ok=True)
            name = f"{time.time_ns():020d}-{uuid4().hex}"
            (folder / f"{name}.tmp").write_text(json.dumps(message), encoding="utf-8")
            (folder / f"{name}.tmp").rename(folder / f"{name}.json")  # the worker never sees a half-written message

        await asyncio.to_thread(write)

    async def receive(self, queue: str) -> tuple[dict, Path] | None:
        """The oldest message and the handle to delete it once it has been handled, or None when the queue is empty."""
        def read() -> tuple[dict, Path] | None:
            for path in sorted((self._root / queue).glob("*.json")):
                return json.loads(path.read_text(encoding="utf-8")), path
            return None

        return await asyncio.to_thread(read)

    async def delete(self, handle: Path) -> None:
        await asyncio.to_thread(handle.unlink, True)

    def pending(self, queue: str) -> list[dict]:
        """Messages waiting in the queue, oldest first."""
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((self._root / queue).glob("*.json"))]


class AzureTaskQueue:
    """
    The same queues in Azure Storage Queues, which have to exist already. A received message turns invisible for
    VISIBILITY_SECONDS: if the worker dies, it shows up again after that and is retried.
    """

    VISIBILITY_SECONDS = 3600

    def __init__(self, connection_string: str):
        self._connection_string = connection_string

    def _client(self, queue: str) -> QueueClient:
        return QueueClient.from_connection_string(self._connection_string, queue)

    async def send(self, queue: str, message: dict) -> None:
        async with self._client(queue) as client:
            await client.send_message(json.dumps(message))

    async def receive(self, queue: str) -> tuple[dict, tuple] | None:
        async with self._client(queue) as client:
            async for received in client.receive_messages(max_messages=1, visibility_timeout=self.VISIBILITY_SECONDS):
                return json.loads(received.content), (queue, received)
        return None

    async def delete(self, handle: tuple) -> None:
        queue, received = handle
        async with self._client(queue) as client:
            await client.delete_message(received)


def get_task_queue() -> LocalTaskQueue | AzureTaskQueue:
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if connection_string:
        return AzureTaskQueue(connection_string)
    return LocalTaskQueue(Path(os.getenv("LOCAL_STORAGE_DIR", "storage")) / "queues")
