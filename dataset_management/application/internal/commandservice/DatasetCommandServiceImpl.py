from uuid import uuid4

from dataset_management.domain.model.aggregates.UploadedDataset import UploadedDataset
from dataset_management.domain.model.commands.DatasetCommands import UploadDatasetCommand
from dataset_management.domain.repositories.DatasetRepository import DatasetRepository
from shared.infrastructure.queue.task_queue import ETL_QUEUE


class DatasetCommandServiceImpl:

    def __init__(self, repository: DatasetRepository, storage, queue):
        self._repository = repository
        self._storage = storage
        self._queue = queue

    async def upload_dataset(self, command: UploadDatasetCommand) -> UploadedDataset:
        """Stores the file as it came and queues its cleaning; the Job moves the dataset on from 'raw'."""
        filename = UploadedDataset.validate_upload(command.filename, command.content)
        # The stored name is generated: the name the user sent is only kept as a label.
        extension = filename[filename.rfind("."):].lower()
        path = await self._storage.save(f"raw/{uuid4().hex}{extension}", command.content)
        dataset = await self._repository.save(UploadedDataset(filename=filename, storage_path=path))
        try:
            await self._queue.send(ETL_QUEUE, {"task": "etl", "dataset_id": dataset.id})
        except Exception:
            dataset.mark_failed("The processing task could not be queued; upload the file again")
            await self._repository.save(dataset)
            raise
        return dataset
