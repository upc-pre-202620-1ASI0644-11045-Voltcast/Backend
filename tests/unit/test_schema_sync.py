"""The startup sync brings a database created by an earlier version up to date."""
import asyncio
import tempfile
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from cell_management.infrastructure.persistence.schema_sync import sync_cell_management_schema

# Tables as the previous version created them: no is_visible, cells active by default.
_OLD_SCHEMA = [
    "CREATE TABLE cell (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL, barcode_value VARCHAR(100), is_active BOOLEAN NOT NULL DEFAULT 1)",
    "CREATE TABLE component (id INTEGER PRIMARY KEY, type INTEGER NOT NULL, serial_code VARCHAR(50) NOT NULL, is_active BOOLEAN NOT NULL DEFAULT 1, cell_id INTEGER)",
    "INSERT INTO cell (id, name, is_active) VALUES (1, 'A1', 1), (2, 'A2', 1), (3, 'A3', 1)",
    # A1: cathode + anode. A2: only a cathode. A3: cathode + a disabled anode.
    "INSERT INTO component (id, type, serial_code, is_active, cell_id) VALUES "
    "(1, 0, 'CAT-1', 1, 1), (2, 1, 'ANO-1', 1, 1), (3, 0, 'CAT-2', 1, 2), (4, 0, 'CAT-3', 1, 3), (5, 1, 'ANO-3', 0, 3)",
]


async def _run() -> tuple[set[str], set[str], list[tuple[int, int, int]]]:
    path = Path(tempfile.mkdtemp(prefix="voltcast-sync-")) / "old.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{path.as_posix()}")
    async with engine.begin() as connection:
        for statement in _OLD_SCHEMA:
            await connection.execute(text(statement))
    for _ in range(2):  # runs on every start: the second run must be harmless
        async with engine.begin() as connection:
            await sync_cell_management_schema(connection)
    async with engine.connect() as connection:
        columns = await connection.run_sync(
            lambda sync: tuple({c["name"] for c in inspect(sync).get_columns(t)} for t in ("cell", "component"))
        )
        cells = (await connection.execute(text("SELECT id, is_active, is_visible FROM cell ORDER BY id"))).all()
    await engine.dispose()
    return columns[0], columns[1], [tuple(row) for row in cells]


def test_adds_the_new_columns_and_recomputes_the_cell_status():
    cell_columns, component_columns, cells = asyncio.run(_run())

    assert "is_visible" in cell_columns and "is_visible" in component_columns
    # Only A1 has an active cathode and anode; everything stays visible.
    assert cells == [(1, 1, 1), (2, 0, 1), (3, 0, 1)]
