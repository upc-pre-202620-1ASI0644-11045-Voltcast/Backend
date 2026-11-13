import json
from uuid import uuid4

from dataset_management.domain.model.aggregates.UploadedDataset import DatasetStatus, UploadedDataset
from dataset_management.domain.model.commands.DatasetCommands import UploadDatasetCommand
from dataset_management.domain.repositories.DatasetRepository import DatasetRepository
from shared.infrastructure.queue.task_queue import ETL_QUEUE


class DatasetCommandServiceImpl:

    def __init__(self, repository: DatasetRepository, storage, queue, training_in_progress):
        self._repository = repository
        self._training_in_progress = training_in_progress  # async () -> bool, so this module does not depend on forecasting
        self._storage = storage
        self._queue = queue

    async def upload_dataset(self, command: UploadDatasetCommand) -> UploadedDataset:
        """Stores the file as it came and queues its cleaning; the Job moves the dataset on from 'raw'."""
        filename = UploadedDataset.validate_upload(command.filename, command.content)
        await self._ensure_no_training()
        # The stored name is generated: the name the user sent is only kept as a label.
        extension = filename[filename.rfind("."):].lower()
        path = await self._storage.save(f"raw/{uuid4().hex}{extension}", command.content)
        extra_paths = []
        for extra_name, extra_content in command.extra_files:
            extra_name = UploadedDataset.validate_upload(extra_name, extra_content)
            extra_paths.append(await self._storage.save(f"raw/{uuid4().hex}{extra_name[extra_name.rfind('.'):].lower()}", extra_content))
        if command.base_dataset_id is not None:
            base = await self._repository.find_by_id(command.base_dataset_id)
            if base is None or base.upload_status != DatasetStatus.READY:
                raise ValueError("The dataset to complement does not exist or is not ready")
        dataset = await self._repository.save(
            UploadedDataset(
                filename=filename, storage_path=path, base_dataset_id=command.base_dataset_id,
                extra_paths=json.dumps(extra_paths) if extra_paths else None,
            )
        )
        try:
            message = {"task": "etl", "dataset_id": dataset.id}
            if command.auto_confirm:
                message["confirmed"] = True
            await self._queue.send(ETL_QUEUE, message)
        except Exception:
            dataset.mark_failed("The processing task could not be queued; upload the file again")
            await self._repository.save(dataset)
            raise
        return dataset

    async def confirm_merge(self, dataset_id: int) -> UploadedDataset:
        """The user accepted the merge shown for the dataset: queues the second pass of the ETL."""
        dataset = await self._repository.find_by_id(dataset_id)
        if dataset is None:
            raise LookupError("Dataset not found")
        await self._ensure_no_training()
        dataset.confirm_merge()
        await self._repository.save(dataset)
        try:
            await self._queue.send(ETL_QUEUE, {"task": "etl", "dataset_id": dataset.id, "confirmed": True})
        except Exception:
            dataset.mark_failed("The processing task could not be queued; upload the file again")
            await self._repository.save(dataset)
            raise
        return dataset

    async def _ensure_no_training(self) -> None:
        if await self._training_in_progress():
            raise ValueError("A training is in progress; wait for it to finish before uploading a new file")
