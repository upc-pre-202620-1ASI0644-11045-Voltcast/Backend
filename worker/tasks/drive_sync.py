import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath
from uuid import uuid4

from sqlalchemy import select

from dataset_management.application.internal.commandservice.DatasetCommandServiceImpl import DatasetCommandServiceImpl
from dataset_management.domain.model.aggregates.UploadedDataset import (
    ALLOWED_EXTENSIONS, DatasetStatus, MAX_UPLOAD_BYTES, UploadedDataset,
)
from dataset_management.domain.model.commands.DatasetCommands import UploadDatasetCommand
from dataset_management.infrastructure.persistence.repositories.DatasetRepositoryImpl import DatasetRepositoryImpl
from drive_integration.application.internal.DriveServiceImpl import utcnow
from drive_integration.domain.model.aggregates.DriveConnection import (
    ERROR_INVALID_GRANT, ERROR_SYNC_FAILED, FILE_CONSUMED, FILE_HELD, FILE_PENDING, FILE_REJECTED,
    DriveConnection, DriveFile,
)
from shared.infrastructure.google import drive_client as gdrive, token_cipher
from shared.infrastructure.persistence.configuration.database_configuration import AsyncSessionLocal
from shared.infrastructure.queue.task_queue import get_task_queue
from shared.infrastructure.storage.file_storage import get_file_storage
from voltage_forecasting.infrastructure.persistence.repositories.TrainingRepositoryImpl import TrainingRepositoryImpl
from worker.etl import config
from worker.etl.excel import read_sections
from worker.etl.pipeline import check_continuity, check_not_future, date_range

logger = logging.getLogger(__name__)

RETRAIN_MIN_NEW_DAYS = 30  # new days of records, beyond the last dataset, before a new dataset (and its training) is made
SETTLE = timedelta(seconds=60)  # a file modified more recently may still be uploading


async def process_drive_sync() -> None:
    """
    One run of the daily Job. Brings the new Excel files of the Drive folder, keeps the ones that continue the data
    and, once they add RETRAIN_MIN_NEW_DAYS days, makes ONE dataset with all of them: the ETL cleans it and, as with any
    ready dataset, trains on it. Safe to repeat: every file version is looked at once.
    """
    async with AsyncSessionLocal() as session:
        await sync_drive(session, get_file_storage(), get_task_queue())


async def sync_drive(session, storage, queue) -> None:
    connection = await session.get(DriveConnection, 1)
    if connection is None or connection.error == ERROR_INVALID_GRANT:
        return  # nothing to sync, or the account has to be connected again: no retries in a loop
    try:
        access_token = await _access_token(session, connection)
        await _collect(session, storage, access_token)
        await _create_dataset_if_due(session, storage, queue)
        error = None
    except gdrive.InvalidGrant:
        error = ERROR_INVALID_GRANT
    except Exception:
        logger.exception("The Drive sync failed")
        error = ERROR_SYNC_FAILED
    if error:
        await session.rollback()
    connection = await session.get(DriveConnection, 1)  # may have been disconnected or reconnected meanwhile
    if connection is not None:
        connection.error = error
        if error is None:
            connection.last_sync_at = utcnow()
        await session.commit()


async def _access_token(session, connection) -> str:
    tokens = await gdrive.refresh(token_cipher.decrypt(connection.refresh_token))
    if tokens.get("refresh_token"):  # Google keeps it, but if it sends another one that is the valid one
        connection.refresh_token = token_cipher.encrypt(tokens["refresh_token"])
        await session.commit()
    return tokens["access_token"]


async def _base(session, storage) -> tuple[UploadedDataset, object, object] | None:
    """The latest ready dataset and the days it covers: what new files have to continue."""
    dataset = (await session.execute(
        select(UploadedDataset).where(UploadedDataset.upload_status == DatasetStatus.READY).order_by(UploadedDataset.id.desc()).limit(1)
    )).scalars().first()
    if dataset is None:
        return None
    summary = json.loads(await storage.read(str(PurePosixPath(dataset.processed_path).with_name("summary.json"))))
    return dataset, datetime.fromisoformat(summary["date_from"]).date(), datetime.fromisoformat(summary["date_to"]).date()


async def _look_at(session, storage, access_token: str, item: dict) -> DriveFile:
    """Downloads one new file version and records what it is: its days, or why it is rejected."""
    row = DriveFile(item_id=item["id"], version=item["version"], name=item["name"], status=FILE_REJECTED)
    suffix = PurePosixPath(item["name"]).suffix.lower()
    if item.get("size", 0) > MAX_UPLOAD_BYTES:
        row.reason = f"The file exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit"
        return row
    content = await gdrive.download(access_token, item["id"])
    try:
        UploadedDataset.validate_upload(item["name"], content)
        sections = await asyncio.to_thread(read_sections, content, suffix)
        check_not_future(sections)
        row.date_from, row.date_to = date_range(sections)
    except ValueError as error:  # SchemaError is one: the message says what is wrong with the file
        row.reason = str(error)[:500]
        return row
    except Exception:
        logger.exception("Drive file %s could not be read", item["name"])
        row.reason = "The file could not be read"
        return row
    row.status = FILE_HELD  # until it is checked against the days before it
    row.storage_path = await storage.save(f"drive/{uuid4().hex}{suffix}", content)
    return row


async def _collect(session, storage, access_token: str) -> None:
    items = await gdrive.list_folder(access_token, gdrive.folder_id())
    if items is None:  # a wrong or deleted folder is not "nothing new": it must show as a failure, not as a healthy sync
        raise RuntimeError("The Drive folder does not exist, is in the trash or is not shared with the connected account")
    known = {tuple(pair) for pair in (await session.execute(select(DriveFile.item_id, DriveFile.version))).all()}
    settled = datetime.now(timezone.utc) - SETTLE
    for item in sorted(items, key=lambda i: i["modified"]):
        if PurePosixPath(item["name"]).suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        if (item["id"], item["version"]) in known or datetime.fromisoformat(item["modified"]) > settled:
            continue
        session.add(await _look_at(session, storage, access_token, item))
        await session.commit()  # one file at a time: a failure later does not lose what was already downloaded

    # Held files (a gap before them) are checked again: the days they were missing may have arrived.
    held = (await session.execute(
        select(DriveFile).where(DriveFile.status == FILE_HELD).order_by(DriveFile.date_from, DriveFile.id)
    )).scalars().all()
    if not held:
        return  # nothing to check: the base summary is not read from storage on a run without held files
    base = await _base(session, storage)
    pending = (await session.execute(select(DriveFile).where(DriveFile.status == FILE_PENDING))).scalars().all()
    frontier = max([f.date_to for f in pending] + ([base[2]] if base else []), default=None)
    for file in held:
        if frontier is None:  # the first data ever: nothing to continue
            file.status, file.reason = FILE_PENDING, None
        elif file.date_to <= frontier:
            file.status, file.reason = FILE_REJECTED, f"The file adds no days after {frontier}, the last day of the data"
        else:
            try:
                check_continuity(frontier, (file.date_from, file.date_to))
            except ValueError as error:
                file.reason = str(error)[:500]  # stays held
                continue
            file.status, file.reason = FILE_PENDING, None  # the gap that held it is gone
        frontier = max(frontier, file.date_to) if frontier else file.date_to
    await session.commit()


async def _create_dataset_if_due(session, storage, queue) -> None:
    pending = (await session.execute(
        select(DriveFile).where(DriveFile.status == FILE_PENDING).order_by(DriveFile.date_from, DriveFile.id)
    )).scalars().all()
    if not pending:
        return
    base = await _base(session, storage)
    last_day = max(f.date_to for f in pending)
    if base:
        new_days = (last_day - base[2]).days
        due = new_days >= RETRAIN_MIN_NEW_DAYS
    else:  # the first dataset: it needs what a model can be trained with
        new_days = (last_day - pending[0].date_from).days + 1
        due = new_days >= config.MIN_DAYS
    if not due:
        logger.info("Drive: %s days of new records, waiting for more before a dataset is made", new_days)
        return
    files = [(f.name, await storage.read(f.storage_path)) for f in pending]
    service = DatasetCommandServiceImpl(
        DatasetRepositoryImpl(session), storage, queue, TrainingRepositoryImpl(session).exists_running
    )
    try:
        dataset = await service.upload_dataset(UploadDatasetCommand(
            filename=files[0][0], content=files[0][1], base_dataset_id=base[0].id if base else None,
            auto_confirm=True, extra_files=tuple(files[1:]),
        ))
    except ValueError as error:  # a training is in progress: the files stay pending for the next run
        logger.info("Drive: the dataset was not created (%s)", error)
        return
    for file in pending:
        file.status, file.dataset_id = FILE_CONSUMED, dataset.id
    await session.commit()
    logger.info("Drive: dataset %s made from %s files", dataset.id, len(pending))
