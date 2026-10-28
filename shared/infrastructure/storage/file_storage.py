import asyncio
import os
from pathlib import Path


class LocalFileStorage:
    """
    Stores the files on the local disk, in a folder shared by the API and the worker.
    shortcut: local disk only, it does not survive a container restart or reach the Job in Azure; the Azure Blob
    Storage implementation replaces it in the cloud setup.
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


def get_file_storage() -> LocalFileStorage:
    return LocalFileStorage(Path(os.getenv("LOCAL_STORAGE_DIR", "storage")))
