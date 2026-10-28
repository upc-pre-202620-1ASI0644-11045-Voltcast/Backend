from datetime import date, datetime
from typing import Protocol

from voltage_forecasting.domain.model.aggregates.MlModel import MlModel
from voltage_forecasting.domain.model.aggregates.ModelEvaluation import ModelEvaluation
from voltage_forecasting.domain.model.aggregates.Prediction import Prediction


class ForecastRepository(Protocol):

    async def find_active_model(self) -> MlModel | None: ...
    async def prediction_date_range(self, model_id: int) -> tuple[date, date] | None: ...
    async def find_predictions(
        self, model_id: int, start: datetime, end_exclusive: datetime, cell_id: int | None
    ) -> list[tuple[Prediction, str]]: ...
    async def find_latest_evaluation(self, model_id: int) -> ModelEvaluation | None: ...
    async def evaluation_error_stats(self, evaluation_id: int) -> tuple[int, float, float, float | None]:
        """(samples, mean squared error, mean absolute error, mean absolute percentage error as a fraction)."""
        ...
