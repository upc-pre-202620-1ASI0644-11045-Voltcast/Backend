import json
from pathlib import PurePosixPath

from dataset_management.domain.model.aggregates.UploadedDataset import UploadedDataset, DatasetStatus
from dataset_management.domain.model.queries.DatasetQueries import GetDatasetByIdQuery, GetAllDatasetsQuery
from dataset_management.domain.repositories.DatasetRepository import DatasetRepository


class DatasetQueryServiceImpl:

    def __init__(self, repository: DatasetRepository, storage):
        self._repository = repository
        self._storage = storage

    async def get_dataset_by_id(self, query: GetDatasetByIdQuery) -> UploadedDataset | None:
        return await self._repository.find_by_id(query.dataset_id)

    async def get_all_datasets(self, query: GetAllDatasetsQuery) -> list[UploadedDataset]:
        return await self._repository.find_all()

    async def get_summary(self, dataset: UploadedDataset) -> dict | None:
        """What the cleaning found in a ready dataset: cells per section and covered dates (US003)."""
        if dataset.upload_status != DatasetStatus.READY or not dataset.processed_path:
            return None
        try:
            path = str(PurePosixPath(dataset.processed_path).with_name("summary.json"))
            return json.loads(await self._storage.read(path))
        except FileNotFoundError:
            return None
