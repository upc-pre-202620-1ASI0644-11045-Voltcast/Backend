import asyncio
import json
import logging
from io import BytesIO

from sqlalchemy import select

from cell_management.domain.model.aggregates.Cell import Cell
from dataset_management.domain.model.aggregates.UploadedDataset import DatasetStatus
from dataset_management.infrastructure.persistence.repositories.DatasetRepositoryImpl import DatasetRepositoryImpl
from iam.domain.model.aggregates.User import User  # noqa: F401  the table `executed_by` points to must be known
from shared.infrastructure.persistence.configuration.database_configuration import AsyncSessionLocal
from shared.infrastructure.queue.task_queue import get_task_queue
from voltage_forecasting.application.internal.commandservice.TrainingCommandServiceImpl import TrainingCommandServiceImpl
from voltage_forecasting.domain.model.commands.ForecastingCommands import RequestTrainingCommand
from voltage_forecasting.infrastructure.persistence.repositories.TrainingRepositoryImpl import TrainingRepositoryImpl
from worker.etl.excel import SchemaError, read_sections
from worker.etl.pipeline import build_silver, raw_row_count

logger = logging.getLogger(__name__)


def _parquet(df) -> bytes:
    buffer = BytesIO()
    df.to_parquet(buffer, engine="pyarrow", index=False)
    return buffer.getvalue()


async def _ensure_cells(session, names: list[str]) -> int:
    """Registers the cells of the file that do not exist yet (inactive, without components); returns how many."""
    existing = set((await session.execute(select(Cell.name).where(Cell.name.in_(names)))).scalars())
    missing = [n for n in names if n not in existing]
    session.add_all(Cell(name=n, is_active=False, is_visible=True) for n in missing)
    await session.commit()
    return len(missing)


async def process_etl(message: dict, storage) -> None:
    """
    Cleans an uploaded dataset: raw -> cleaning -> ready | failed (US001-US004). Leaves the Silver table, the level
    shifts, the split and a summary next to each other in `processed/<dataset id>/`. A file the user can fix ends as
    `failed` with the cause; an infrastructure error propagates, so the message stays in the queue and is retried.
    """
    dataset_id = message["dataset_id"]
    async with AsyncSessionLocal() as session:
        repository = DatasetRepositoryImpl(session)
        dataset = await repository.find_by_id(dataset_id)
        if dataset is None or dataset.upload_status not in (DatasetStatus.RAW, DatasetStatus.CLEANING):
            logger.warning("Dataset %s is missing or already handled; message dropped", dataset_id)
            return

        dataset.start_cleaning()
        await repository.save(dataset)
        try:
            sections = await asyncio.to_thread(read_sections, await storage.read(dataset.storage_path))
            result = await asyncio.to_thread(build_silver, sections)
            folder = f"processed/{dataset.id}"
            silver_path = await storage.save(f"{folder}/voltajes_silver.parquet", _parquet(result.silver))
            await storage.save(f"{folder}/saltos_nivel.parquet", _parquet(result.level_shifts))
            await storage.save(f"{folder}/split.json", json.dumps(result.split).encode())
            created = await _ensure_cells(session, result.cell_names)
            await storage.save(
                f"{folder}/summary.json", json.dumps({**result.summary, "new_cells": created}).encode()
            )
            dataset.mark_ready(silver_path, raw_row_count(sections), len(result.silver))
            logger.info("Dataset %s ready: %s (%s new cells)", dataset.id, result.summary, created)
        except SchemaError as error:
            dataset.mark_failed(str(error))
            logger.info("Dataset %s rejected: %s", dataset_id, error)
        except Exception:
            logger.exception("Dataset %s failed with an unexpected error", dataset_id)
            await session.rollback()
            dataset.mark_failed("The file could not be processed; check it and upload it again")
        await repository.save(dataset)
        if dataset.upload_status == DatasetStatus.READY:
            await _request_training(session, repository, dataset.id)


async def _request_training(session, dataset_repository, dataset_id: int) -> None:
    """A cleaned file is trained on right away, as the system (no user). If it cannot be queued, the dataset stays ready and a person can request it."""
    try:
        service = TrainingCommandServiceImpl(TrainingRepositoryImpl(session), dataset_repository, get_task_queue())
        execution = await service.request_training(RequestTrainingCommand(dataset_id=dataset_id, user_id=None))
        logger.info("Training %s queued for dataset %s", execution.id, dataset_id)
    except Exception:
        logger.exception("Dataset %s is ready but its training was not queued", dataset_id)
