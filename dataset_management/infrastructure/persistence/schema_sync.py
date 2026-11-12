from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncConnection

_STATUSES = "'raw','cleaning','awaiting_confirmation','ready','failed'"


async def sync_dataset_management_schema(connection: AsyncConnection) -> None:
    """
    Brings a database created by an earlier version up to date: the dataset a file complements and the status where
    the user confirms the merge. create_all() does not touch existing tables. Safe to run on every start.
    """
    columns = await connection.run_sync(lambda sync: {c["name"] for c in inspect(sync).get_columns("uploaded_dataset")})
    if "base_dataset_id" not in columns:
        await connection.execute(text("ALTER TABLE uploaded_dataset ADD COLUMN base_dataset_id SMALLINT NULL"))
        if connection.dialect.name == "mysql":
            await connection.execute(text(
                "ALTER TABLE uploaded_dataset ADD CONSTRAINT fk_uploaded_dataset_base "
                "FOREIGN KEY (base_dataset_id) REFERENCES uploaded_dataset (id)"
            ))
    if "extra_paths" not in columns:
        await connection.execute(text("ALTER TABLE uploaded_dataset ADD COLUMN extra_paths TEXT NULL"))
    if connection.dialect.name == "mysql":  # elsewhere the status is plain text
        await connection.execute(text(
            f"ALTER TABLE uploaded_dataset MODIFY upload_status ENUM({_STATUSES}) NOT NULL DEFAULT 'raw'"
        ))
