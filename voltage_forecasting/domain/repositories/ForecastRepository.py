from datetime import date, datetime
from typing import Protocol

from voltage_forecasting.domain.model.aggregates.MlModel import MlModel
from voltage_forecasting.domain.model.aggregates.ModelEvaluation import ModelEvaluationResult
from voltage_forecasting.domain.model.aggregates.Prediction import Prediction
from voltage_forecasting.domain.model.aggregates.TrainingExecution import TrainingExecution


class ForecastRepository(Protocol):

    async def find_active_model(self) -> MlModel | None: ...
    async def prediction_date_range(self, model_id: int) -> tuple[date, date] | None: ...
    async def find_predictions(
        self, model_id: int, start: datetime, end_exclusive: datetime, cell_id: int | None
    ) -> list[tuple[Prediction, str]]: ...
    async def find_latest_success(self, model_id: int) -> TrainingExecution | None:
        """The latest finished run of the model: its accuracy over the validation days."""
        ...
    async def evaluation_date_range(self, model_id: int) -> tuple[date, date] | None:
        """First and last day of the model's backtest against the measured voltage."""
        ...
    async def find_evaluation(self, model_id: int, day: date) -> list[tuple[ModelEvaluationResult, str]]:
        """Forecast and measured voltage of every cell on a day of the backtest."""
        ...
