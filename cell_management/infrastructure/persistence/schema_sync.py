from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncConnection

# Columns added after the tables were first created: create_all() does not touch existing tables.
_ADDED_COLUMNS = {
    "cell": {"is_visible": "BOOLEAN NOT NULL DEFAULT 1"},
    "component": {"is_visible": "BOOLEAN NOT NULL DEFAULT 1"},
}

# A cell is active only while it has an active cathode (type 0) and anode (type 1) assigned.
_RECOMPUTE_CELL_STATUS = text(
    """
    UPDATE cell SET is_active = CASE
        WHEN EXISTS (SELECT 1 FROM component c WHERE c.cell_id = cell.id AND c.is_active = 1 AND c.type = 0)
         AND EXISTS (SELECT 1 FROM component c WHERE c.cell_id = cell.id AND c.is_active = 1 AND c.type = 1)
        THEN 1 ELSE 0 END
    """
)


async def sync_cell_management_schema(connection: AsyncConnection) -> None:
    """
    Brings a database created by an earlier version up to date: adds the missing columns and
    recomputes every cell's status from its components (cells used to be active by default).
    Safe to run on every start.
    """
    existing = await connection.run_sync(
        lambda sync: {table: {c["name"] for c in inspect(sync).get_columns(table)} for table in _ADDED_COLUMNS}
    )
    for table, columns in _ADDED_COLUMNS.items():
        for column, ddl in columns.items():
            if column not in existing[table]:
                await connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
    await connection.execute(_RECOMPUTE_CELL_STATUS)
