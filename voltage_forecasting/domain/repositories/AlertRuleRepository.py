from typing import Protocol

from voltage_forecasting.domain.model.aggregates.AlertRule import AlertRule


class AlertRuleRepository(Protocol):

    async def save(self, rule: AlertRule) -> AlertRule:
        """Persist an alert rule and return it."""
        ...
    async def find_active(self, cell_id: int | None) -> list[AlertRule]:
        """List the active rules of a cell, or the general ones if no cell is given."""
        ...
    async def find_all_active(self) -> list[AlertRule]:
        """List every active rule."""
        ...
