from datetime import date
from dataclasses import asdict

from voltage_forecasting.application.internal.queryservice.ForecastQueryServiceImpl import ForecastView, MetricsView
from voltage_forecasting.domain.model.aggregates.AlertRule import AlertRule
from voltage_forecasting.domain.model.aggregates.TrainingExecution import TrainingExecution
from voltage_forecasting.domain.model.commands.ForecastingCommands import RequestTrainingCommand, CreateAlertRuleCommand
from voltage_forecasting.domain.model.queries.ForecastingQueries import (
    GetForecastsQuery,
    GetModelMetricsQuery,
    GetTrainingByIdQuery,
    GetAllTrainingsQuery,
    GetAlertRulesQuery,
)
from voltage_forecasting.interface.api.rest.resources.ForecastingResource import (
    AlertRuleRequest,
    AlertRuleResponse,
    ForecastResponse,
    MetricsResponse,
    TrainingRequest,
    TrainingResponse,
)


class ForecastingResourceAssembler:

    @staticmethod
    def to_request_training_command(request: TrainingRequest, user_id: int) -> RequestTrainingCommand:
        return RequestTrainingCommand(dataset_id=request.dataset_id, user_id=user_id)

    @staticmethod
    def to_create_alert_rule_command(request: AlertRuleRequest) -> CreateAlertRuleCommand:
        return CreateAlertRuleCommand(max_voltage=request.max_voltage, cell_id=request.cell_id)

    @staticmethod
    def to_forecasts_query(date_from: date | None, date_to: date | None, cell_id: int | None,
                           exceeds: bool | None = None) -> GetForecastsQuery:
        return GetForecastsQuery(date_from=date_from, date_to=date_to, cell_id=cell_id, exceeds=exceeds)

    @staticmethod
    def to_metrics_query() -> GetModelMetricsQuery:
        return GetModelMetricsQuery()

    @staticmethod
    def to_training_by_id_query(training_id: int) -> GetTrainingByIdQuery:
        return GetTrainingByIdQuery(training_id=training_id)

    @staticmethod
    def to_all_trainings_query() -> GetAllTrainingsQuery:
        return GetAllTrainingsQuery()

    @staticmethod
    def to_alert_rules_query() -> GetAlertRulesQuery:
        return GetAlertRulesQuery()

    @staticmethod
    def to_training_response(execution: TrainingExecution) -> TrainingResponse:
        return TrainingResponse.model_validate(execution)

    @staticmethod
    def to_alert_rule_response(rule: AlertRule) -> AlertRuleResponse:
        return AlertRuleResponse.model_validate(rule)

    @staticmethod
    def to_forecast_response(view: ForecastView) -> ForecastResponse:
        return ForecastResponse(
            model=view.model, retraining=view.retraining, message=view.message,
            available_from=view.available_from, available_to=view.available_to,
            items=[asdict(item) for item in view.items],
        )

    @staticmethod
    def to_metrics_response(view: MetricsView) -> MetricsResponse:
        return MetricsResponse(
            model=view.model, retraining=view.retraining, message=view.message,
            mse=view.mse, rmse=view.rmse, mae=view.mae, mape=view.mape, r2=view.r2,
        )
