from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voltage_forecasting.domain.model.aggregates.AlertRule import AlertRule


class AlertRuleRepositoryImpl:

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, rule: AlertRule) -> AlertRule:
        self._session.add(rule)
        await self._session.commit()
        await self._session.refresh(rule)
        return rule

    async def find_active(self, cell_id: int | None) -> list[AlertRule]:
        scope = AlertRule.cell_id.is_(None) if cell_id is None else AlertRule.cell_id == cell_id
        result = await self._session.execute(select(AlertRule).where(AlertRule.is_active.is_(True), scope))
        return list(result.scalars().all())

    async def find_all_active(self) -> list[AlertRule]:
        result = await self._session.execute(
            select(AlertRule).where(AlertRule.is_active.is_(True)).order_by(AlertRule.id)
        )
        return list(result.scalars().all())
