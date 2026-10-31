"""A database created before datasets could complement each other gets the new column on start."""
import asyncio
import tempfile
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from dataset_management.infrastructure.persistence.schema_sync import sync_dataset_management_schema

_OLD_TABLE = "CREATE TABLE uploaded_dataset (id INTEGER PRIMARY KEY, filename VARCHAR(255) NOT NULL, upload_status VARCHAR(20) NOT NULL)"


async def _run() -> set[str]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{(Path(tempfile.mkdtemp(prefix='voltcast-sync-')) / 'old.db').as_posix()}")
    async with engine.begin() as connection:
        await connection.execute(text(_OLD_TABLE))
    for _ in range(2):  # runs on every start: the second run must be harmless
        async with engine.begin() as connection:
            await sync_dataset_management_schema(connection)
    async with engine.connect() as connection:
        columns = await connection.run_sync(lambda sync: {c["name"] for c in inspect(sync).get_columns("uploaded_dataset")})
    await engine.dispose()
    return columns


def test_adds_the_column_of_the_dataset_a_file_complements():
    assert "base_dataset_id" in asyncio.run(_run())
