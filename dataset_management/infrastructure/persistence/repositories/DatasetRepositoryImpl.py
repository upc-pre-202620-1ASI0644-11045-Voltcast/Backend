from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dataset_management.domain.model.aggregates.UploadedDataset import UploadedDataset


class DatasetRepositoryImpl:

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, dataset: UploadedDataset) -> UploadedDataset:
        self._session.add(dataset)
        await self._session.commit()
        await self._session.refresh(dataset)
        return dataset

    async def find_by_id(self, dataset_id: int) -> UploadedDataset | None:
        result = await self._session.execute(select(UploadedDataset).where(UploadedDataset.id == dataset_id))
        return result.scalar_one_or_none()

    async def find_all(self) -> list[UploadedDataset]:
        result = await self._session.execute(select(UploadedDataset).order_by(UploadedDataset.id.desc()))
        return list(result.scalars().all())
