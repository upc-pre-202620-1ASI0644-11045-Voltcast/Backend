from cell_management.domain.repositories.CellRepository import CellRepository
from voltage_forecasting.domain.model.aggregates.AlertRule import AlertRule
from voltage_forecasting.domain.model.commands.ForecastingCommands import CreateAlertRuleCommand
from voltage_forecasting.domain.repositories.AlertRuleRepository import AlertRuleRepository


class AlertRuleCommandServiceImpl:

    def __init__(self, repository: AlertRuleRepository, cell_repository: CellRepository):
        self._repository = repository
        self._cell_repo = cell_repository

    async def create_rule(self, command: CreateAlertRuleCommand) -> AlertRule:
        """Sets the maximum voltage of a cell, or the general one when no cell is given; it replaces the previous one."""
        AlertRule.validate_max_voltage(command.max_voltage)
        if command.cell_id is not None and not await self._cell_repo.find_by_id(command.cell_id):
            raise ValueError(f"Cell not found: {command.cell_id}")
        for previous in await self._repository.find_active(command.cell_id):
            previous.is_active = False
            await self._repository.save(previous)
        return await self._repository.save(AlertRule(cell_id=command.cell_id, max_voltage=command.max_voltage))
