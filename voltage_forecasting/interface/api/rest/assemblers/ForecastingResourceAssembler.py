from datetime import date
from dataclasses import asdict

from voltage_forecasting.application.internal.queryservice.ForecastQueryServiceImpl import (
    EvaluationSeriesView,
    EvaluationView,
    ForecastView,
    MetricsView,
)
from voltage_forecasting.domain.model.aggregates.AlertRule import AlertRule
from voltage_forecasting.domain.model.aggregates.TrainingExecution import TrainingExecution
from voltage_forecasting.domain.model.commands.ForecastingCommands import RequestTrainingCommand, CreateAlertRuleCommand
from voltage_forecasting.domain.model.queries.ForecastingQueries import (
    GetEvaluationQuery,
    GetEvaluationSeriesQuery,
    GetForecastsQuery,
    GetModelMetricsQuery,
    GetTrainingByIdQuery,
    GetAllTrainingsQuery,
    GetAlertRulesQuery,
)
from voltage_forecasting.interface.api.rest.resources.ForecastingResource import (
    AlertRuleRequest,
    AlertRuleResponse,
    EvaluationResponse,
    EvaluationSeriesPointResponse,
    EvaluationSeriesResponse,
    ForecastResponse,
    MetricsResponse,
    TrainingRequest,
    TrainingResponse,
)


class ForecastingResourceAssembler:

    @staticmethod
    def to_request_training_command(request: TrainingRequest, user_id: int) -> RequestTrainingCommand:
        """Build the training request command."""
        return RequestTrainingCommand(dataset_id=request.dataset_id, user_id=user_id)

    @staticmethod
    def to_create_alert_rule_command(request: AlertRuleRequest) -> CreateAlertRuleCommand:
        """Build the create-alert-rule command from the request."""
        return CreateAlertRuleCommand(max_voltage=request.max_voltage, cell_id=request.cell_id)

    @staticmethod
    def to_forecasts_query(date_from: date | None, date_to: date | None, cell_id: int | None,
                           exceeds: bool | None = None) -> GetForecastsQuery:
        """Build the forecasts query from its filters."""
        return GetForecastsQuery(date_from=date_from, date_to=date_to, cell_id=cell_id, exceeds=exceeds)

    @staticmethod
    def to_evaluation_query(day: date | None, limit: int, worst_first: bool) -> GetEvaluationQuery:
        """Build the query for the evaluation of one day."""
        return GetEvaluationQuery(day=day, limit=limit, worst_first=worst_first)

    @staticmethod
    def to_evaluation_series_query(date_from: date | None, date_to: date | None) -> GetEvaluationSeriesQuery:
        """Build the query for the evaluation series of a period."""
        return GetEvaluationSeriesQuery(date_from=date_from, date_to=date_to)

    @staticmethod
    def to_metrics_query() -> GetModelMetricsQuery:
        """Build the model metrics query."""
        return GetModelMetricsQuery()

    @staticmethod
    def to_training_by_id_query(training_id: int) -> GetTrainingByIdQuery:
        """Build the query for one training run."""
        return GetTrainingByIdQuery(training_id=training_id)

    @staticmethod
    def to_all_trainings_query() -> GetAllTrainingsQuery:
        """Build the query for all training runs."""
        return GetAllTrainingsQuery()

    @staticmethod
    def to_alert_rules_query() -> GetAlertRulesQuery:
        """Build the query for the alert rules."""
        return GetAlertRulesQuery()

    @staticmethod
    def to_training_response(execution: TrainingExecution) -> TrainingResponse:
        """Map a training run to its API response."""
        return TrainingResponse.model_validate(execution)

    @staticmethod
    def to_alert_rule_response(rule: AlertRule) -> AlertRuleResponse:
        """Map an alert rule to its API response."""
        return AlertRuleResponse.model_validate(rule)

    @staticmethod
    def to_forecast_response(view: ForecastView) -> ForecastResponse:
        """Map the forecast view to its API response."""
        return ForecastResponse(
            model=view.model, retraining=view.retraining, message=view.message,
            available_from=view.available_from, available_to=view.available_to,
            items=[asdict(item) for item in view.items],
        )

    @staticmethod
    def to_metrics_response(view: MetricsView) -> MetricsResponse:
        """Map the metrics view to its API response."""
        return MetricsResponse(
            model=view.model, retraining=view.retraining, message=view.message,
            mse=view.mse, rmse=view.rmse, mae=view.mae, mape=view.mape, r2=view.r2,
        )

    @staticmethod
    def to_evaluation_series_response(view: EvaluationSeriesView) -> EvaluationSeriesResponse:
        """Map the evaluation series view to its API response."""
        return EvaluationSeriesResponse(
            model=view.model, retraining=view.retraining, message=view.message,
            available_from=view.available_from, available_to=view.available_to,
            items=[
                EvaluationSeriesPointResponse(date=p.day, mean_error_pct=p.mean_error_pct, total_cells=p.total_cells)
                for p in view.items
            ],
        )

    @staticmethod
    def to_evaluation_response(view: EvaluationView) -> EvaluationResponse:
        """Map the daily evaluation view to its API response."""
        return EvaluationResponse(
            model=view.model, retraining=view.retraining, message=view.message,
            available_from=view.available_from, available_to=view.available_to, date=view.day,
            total_cells=view.total_cells, mean_error_pct=view.mean_error_pct, items=[asdict(item) for item in view.items],
        )
