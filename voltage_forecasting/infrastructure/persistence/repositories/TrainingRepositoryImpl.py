from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voltage_forecasting.domain.model.aggregates.MlModel import MlModel
from voltage_forecasting.domain.model.aggregates.TrainingExecution import TrainingExecution, TrainingStatus


class TrainingRepositoryImpl:

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_training(self, model: MlModel, execution: TrainingExecution) -> TrainingExecution:
        self._session.add(model)
        await self._session.flush()
        execution.model_id = model.id
        self._session.add(execution)
        await self._session.commit()
        await self._session.refresh(execution)
        return execution

    async def save(self, execution: TrainingExecution) -> TrainingExecution:
        self._session.add(execution)
        await self._session.commit()
        await self._session.refresh(execution)
        return execution

    async def find_by_id(self, training_id: int) -> TrainingExecution | None:
        result = await self._session.execute(select(TrainingExecution).where(TrainingExecution.id == training_id))
        return result.scalar_one_or_none()

    async def find_all(self) -> list[TrainingExecution]:
        result = await self._session.execute(select(TrainingExecution).order_by(TrainingExecution.id.desc()))
        return list(result.scalars().all())

    async def exists_running(self) -> bool:
        result = await self._session.execute(
            select(TrainingExecution.id).where(TrainingExecution.status == TrainingStatus.RUNNING).limit(1)
        )
        return result.first() is not None
