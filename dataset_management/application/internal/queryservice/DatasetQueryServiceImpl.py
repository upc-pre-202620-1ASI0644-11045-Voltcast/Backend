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
        """Ready: what the cleaning found, cells per section and covered dates (US003). Awaiting confirmation: what the merge would do."""
        try:
            if dataset.upload_status == DatasetStatus.READY and dataset.processed_path:
                return json.loads(await self._storage.read(str(PurePosixPath(dataset.processed_path).with_name("summary.json"))))
            if dataset.upload_status == DatasetStatus.AWAITING_CONFIRMATION:
                return json.loads(await self._storage.read(f"processed/{dataset.id}/merge.json"))
        except FileNotFoundError:
            pass
        return None
