from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cell_management.domain.model.aggregates.Cell import Cell
from voltage_forecasting.domain.model.aggregates.MlModel import MlModel
from voltage_forecasting.domain.model.aggregates.ModelEvaluation import ModelEvaluation, ModelEvaluationResult
from voltage_forecasting.domain.model.aggregates.Prediction import Prediction
from voltage_forecasting.domain.model.aggregates.TrainingExecution import TrainingExecution, TrainingStatus


class ForecastRepositoryImpl:

    def __init__(self, session: AsyncSession):
        self._session = session

    async def find_active_model(self) -> MlModel | None:
        result = await self._session.execute(
            select(MlModel).where(MlModel.is_active.is_(True)).order_by(MlModel.id.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def prediction_date_range(self, model_id: int) -> tuple[date, date] | None:
        result = await self._session.execute(
            select(func.min(Prediction.prediction_date), func.max(Prediction.prediction_date))
            .where(Prediction.model_id == model_id)
        )
        first, last = result.one()
        return (first.date(), last.date()) if first is not None else None

    async def find_predictions(
        self, model_id: int, start: datetime, end_exclusive: datetime, cell_id: int | None
    ) -> list[tuple[Prediction, str]]:
        stmt = (
            select(Prediction, Cell.name)
            .join(Cell, Cell.id == Prediction.cell_id)
            .where(
                Prediction.model_id == model_id,
                Prediction.prediction_date >= start,
                Prediction.prediction_date < end_exclusive,
                Cell.is_visible.is_(True),
            )
            .order_by(Prediction.prediction_date, Cell.id)
        )
        if cell_id is not None:
            stmt = stmt.where(Prediction.cell_id == cell_id)
        result = await self._session.execute(stmt)
        return [(prediction, name) for prediction, name in result.all()]

    async def find_latest_success(self, model_id: int) -> TrainingExecution | None:
        result = await self._session.execute(
            select(TrainingExecution)
            .where(TrainingExecution.model_id == model_id, TrainingExecution.status == TrainingStatus.SUCCESS)
            .order_by(TrainingExecution.id.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def evaluation_date_range(self, model_id: int) -> tuple[date, date] | None:
        result = await self._session.execute(
            select(func.min(ModelEvaluationResult.prediction_date), func.max(ModelEvaluationResult.prediction_date))
            .join(ModelEvaluation, ModelEvaluation.id == ModelEvaluationResult.model_evaluation_id)
            .where(ModelEvaluation.model_id == model_id)
        )
        first, last = result.one()
        return (first.date(), last.date()) if first is not None else None

    async def find_evaluation(self, model_id: int, day: date) -> list[tuple[ModelEvaluationResult, str]]:
        start = datetime.combine(day, time.min)
        result = await self._session.execute(
            select(ModelEvaluationResult, Cell.name)
            .join(ModelEvaluation, ModelEvaluation.id == ModelEvaluationResult.model_evaluation_id)
            .join(Cell, Cell.id == ModelEvaluationResult.cell_id)
            .where(
                ModelEvaluation.model_id == model_id,
                ModelEvaluationResult.prediction_date >= start,
                ModelEvaluationResult.prediction_date < start + timedelta(days=1),
                Cell.is_visible.is_(True),
            )
        )
        return [(row, name) for row, name in result.all()]
