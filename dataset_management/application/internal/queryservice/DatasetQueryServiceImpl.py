from dataset_management.domain.model.aggregates.UploadedDataset import UploadedDataset
from dataset_management.domain.model.queries.DatasetQueries import GetDatasetByIdQuery, GetAllDatasetsQuery
from dataset_management.domain.repositories.DatasetRepository import DatasetRepository


class DatasetQueryServiceImpl:

    def __init__(self, repository: DatasetRepository):
        self._repository = repository

    async def get_dataset_by_id(self, query: GetDatasetByIdQuery) -> UploadedDataset | None:
        return await self._repository.find_by_id(query.dataset_id)

    async def get_all_datasets(self, query: GetAllDatasetsQuery) -> list[UploadedDataset]:
        return await self._repository.find_all()
