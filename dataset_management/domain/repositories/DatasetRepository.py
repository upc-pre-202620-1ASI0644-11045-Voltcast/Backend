from typing import Protocol
from dataset_management.domain.model.aggregates.UploadedDataset import UploadedDataset


class DatasetRepository(Protocol):

    async def save(self, dataset: UploadedDataset) -> UploadedDataset:
        """Persist a dataset and return it."""
        ...
    async def find_by_id(self, dataset_id: int) -> UploadedDataset | None:
        """Find a dataset by its id."""
        ...
    async def find_all(self) -> list[UploadedDataset]:
        """List all datasets."""
        ...
