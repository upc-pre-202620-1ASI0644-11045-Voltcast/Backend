from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from math import sqrt

from voltage_forecasting.domain.model.aggregates.MlModel import MlModel
from voltage_forecasting.domain.model.queries.ForecastingQueries import GetForecastsQuery, GetModelMetricsQuery
from voltage_forecasting.domain.repositories.AlertRuleRepository import AlertRuleRepository
from voltage_forecasting.domain.repositories.ForecastRepository import ForecastRepository
from voltage_forecasting.domain.repositories.TrainingRepository import TrainingRepository

RETRAINING_MESSAGE = (
    "The model is being retrained: the latest available version is being used and a new version will be available soon"
)
NO_MODEL_MESSAGE = "No trained model is available yet"


@dataclass
class ForecastItem:
    cell_id: int
    cell_name: str
    date: date
    voltage: float
    max_voltage: float | None
    exceeds: bool


@dataclass
class ForecastView:
    model: MlModel | None
    retraining: bool
    message: str | None
    available_from: date | None = None
    available_to: date | None = None
    items: list[ForecastItem] = field(default_factory=list)


@dataclass
class MetricsView:
    model: MlModel | None
    retraining: bool
    message: str | None
    samples: int = 0
    mse: float | None = None
    rmse: float | None = None
    mae: float | None = None
    mape: float | None = None  # percentage


class ForecastQueryServiceImpl:

    def __init__(self, repository: ForecastRepository, training_repository: TrainingRepository,
                 alert_rule_repository: AlertRuleRepository):
        self._repository = repository
        self._training_repo = training_repository
        self._alert_repo = alert_rule_repository

    async def get_forecasts(self, query: GetForecastsQuery) -> ForecastView:
        """
        Forecasts of the active model for one day or a range (US007, US008). With no date it returns the first
        forecast day, since the full horizon of every cell is too large for a single response.
        """
        model = await self._repository.find_active_model()
        retraining = await self._training_repo.exists_running()
        if not model:
            return ForecastView(None, retraining, NO_MODEL_MESSAGE)
        view = ForecastView(model, retraining, RETRAINING_MESSAGE if retraining else None)

        available = await self._repository.prediction_date_range(model.id)
        if not available:
            return view
        view.available_from, view.available_to = available
        start = query.date_from or available[0]
        end = query.date_to or start
        if end < start:
            raise ValueError("The end date cannot be before the start date")

        rules = await self._alert_repo.find_all_active()
        general = next((r.max_voltage for r in rules if r.cell_id is None), None)
        per_cell = {r.cell_id: r.max_voltage for r in rules if r.cell_id is not None}
        rows = await self._repository.find_predictions(
            model.id, datetime.combine(start, time.min), datetime.combine(end + timedelta(days=1), time.min),
            query.cell_id,
        )
        for prediction, cell_name in rows:
            limit = per_cell.get(prediction.cell_id, general)
            view.items.append(ForecastItem(
                cell_id=prediction.cell_id, cell_name=cell_name, date=prediction.prediction_date.date(),
                voltage=prediction.predicted_voltage, max_voltage=limit,
                exceeds=limit is not None and prediction.predicted_voltage > limit,
            ))
        return view

    async def get_model_metrics(self, query: GetModelMetricsQuery) -> MetricsView:
        """Accuracy of the active model over its latest evaluation against real data (US006)."""
        model = await self._repository.find_active_model()
        retraining = await self._training_repo.exists_running()
        if not model:
            return MetricsView(None, retraining, NO_MODEL_MESSAGE)
        view = MetricsView(model, retraining, RETRAINING_MESSAGE if retraining else None)
        evaluation = await self._repository.find_latest_evaluation(model.id)
        if not evaluation:
            return view
        samples, mse, mae, mape = await self._repository.evaluation_error_stats(evaluation.id)
        if samples:
            view.samples, view.mse, view.rmse, view.mae = samples, mse, sqrt(mse), mae
            view.mape = None if mape is None else mape * 100
        return view
