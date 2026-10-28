from typing import Protocol

from voltage_forecasting.domain.model.aggregates.AlertRule import AlertRule


class AlertRuleRepository(Protocol):

    async def save(self, rule: AlertRule) -> AlertRule: ...
    async def find_active(self, cell_id: int | None) -> list[AlertRule]: ...
    async def find_all_active(self) -> list[AlertRule]: ...
