import asyncio
import os
from pathlib import Path

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob.aio import BlobServiceClient


class LocalFileStorage:
    """
    Stores the files on the local disk, in a folder shared by the API and the worker.
    shortcut: local disk only, it does not survive a container restart or reach the Job in Azure; use
    AZURE_STORAGE_CONNECTION_STRING there.
    """

    def __init__(self, root: Path):
        self._root = root

    async def save(self, path: str, content: bytes) -> str:
        target = self._root / path

        def write() -> None:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)

        await asyncio.to_thread(write)
        return path

    async def read(self, path: str) -> bytes:
        return await asyncio.to_thread((self._root / path).read_bytes)


class AzureBlobStorage:
    """The same files in an Azure Blob Storage container, which has to exist already."""

    def __init__(self, connection_string: str, container: str):
        self._connection_string = connection_string
        self._container = container

    async def save(self, path: str, content: bytes) -> str:
        async with BlobServiceClient.from_connection_string(self._connection_string) as service:
            await service.get_blob_client(self._container, path).upload_blob(content, overwrite=True)
        return path

    async def read(self, path: str) -> bytes:
        async with BlobServiceClient.from_connection_string(self._connection_string) as service:
            try:
                return await (await service.get_blob_client(self._container, path).download_blob()).readall()
            except ResourceNotFoundError as error:
                raise FileNotFoundError(path) from error


def get_file_storage() -> LocalFileStorage | AzureBlobStorage:
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if connection_string:
        return AzureBlobStorage(connection_string, os.getenv("AZURE_STORAGE_CONTAINER", "voltcast"))
    return LocalFileStorage(Path(os.getenv("LOCAL_STORAGE_DIR", "storage")))
