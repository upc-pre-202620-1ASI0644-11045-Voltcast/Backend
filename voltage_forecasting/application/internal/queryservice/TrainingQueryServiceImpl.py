from voltage_forecasting.domain.model.aggregates.AlertRule import AlertRule
from voltage_forecasting.domain.model.aggregates.TrainingExecution import TrainingExecution
from voltage_forecasting.domain.model.queries.ForecastingQueries import (
    GetTrainingByIdQuery,
    GetAllTrainingsQuery,
    GetAlertRulesQuery,
)
from voltage_forecasting.domain.repositories.AlertRuleRepository import AlertRuleRepository
from voltage_forecasting.domain.repositories.TrainingRepository import TrainingRepository


class TrainingQueryServiceImpl:

    def __init__(self, repository: TrainingRepository):
        self._repository = repository

    async def get_training_by_id(self, query: GetTrainingByIdQuery) -> TrainingExecution | None:
        return await self._repository.find_by_id(query.training_id)

    async def get_all_trainings(self, query: GetAllTrainingsQuery) -> list[TrainingExecution]:
        return await self._repository.find_all()


class AlertRuleQueryServiceImpl:

    def __init__(self, repository: AlertRuleRepository):
        self._repository = repository

    async def get_alert_rules(self, query: GetAlertRulesQuery) -> list[AlertRule]:
        return await self._repository.find_all_active()
