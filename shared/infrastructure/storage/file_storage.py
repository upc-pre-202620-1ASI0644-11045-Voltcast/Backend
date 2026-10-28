import asyncio
import os
from pathlib import Path


class LocalFileStorage:
    """
    Stores the uploaded files on the local disk. shortcut: local disk only, it does not survive a
    container restart or reach the Job; the Azure Blob Storage implementation replaces it in the cloud setup.
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


def get_file_storage() -> LocalFileStorage:
    return LocalFileStorage(Path(os.getenv("LOCAL_STORAGE_DIR", "storage")))
