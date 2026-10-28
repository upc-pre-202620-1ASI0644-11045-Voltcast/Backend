from datetime import date, datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cell_management.domain.model.aggregates.Cell import Cell
from voltage_forecasting.domain.model.aggregates.MlModel import MlModel
from voltage_forecasting.domain.model.aggregates.ModelEvaluation import ModelEvaluation, ModelEvaluationResult
from voltage_forecasting.domain.model.aggregates.Prediction import Prediction


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

    async def find_latest_evaluation(self, model_id: int) -> ModelEvaluation | None:
        result = await self._session.execute(
            select(ModelEvaluation).where(ModelEvaluation.model_id == model_id)
            .order_by(ModelEvaluation.id.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def evaluation_error_stats(self, evaluation_id: int) -> tuple[int, float, float, float | None]:
        error = ModelEvaluationResult.predicted_value - ModelEvaluationResult.real_value
        real = ModelEvaluationResult.real_value
        result = await self._session.execute(
            select(
                func.count(),
                func.avg(error * error),
                func.avg(func.abs(error)),
                # A zero real value has no percentage error; avg() skips the NULLs.
                func.avg(case((real != 0, func.abs(error) / func.abs(real)), else_=None)),
            ).where(ModelEvaluationResult.model_evaluation_id == evaluation_id)
        )
        count, mse, mae, mape = result.one()
        return count, mse, mae, mape
