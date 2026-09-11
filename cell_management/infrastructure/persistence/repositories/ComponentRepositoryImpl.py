from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from cell_management.domain.model.aggregates.Component import Component, ComponentAssignmentHistory


class ComponentRepositoryImpl:

    def __init__(self, session: AsyncSession):
        self._session = session

    # ── Component ────────────────────────────────────────────────────────────

    async def save_component(self, component: Component) -> Component:
        self._session.add(component)
        await self._session.commit()
        await self._session.refresh(component)
        return component

    async def find_component_by_id(self, component_id: int) -> Component | None:
        result = await self._session.execute(
            select(Component).where(Component.id == component_id)
        )
        return result.scalar_one_or_none()

    async def find_all_components(
        self,
        component_type: str | None = None,
        cell_id: int | None = None,
        is_active: bool | None = None,
    ) -> list[Component]:
        stmt = select(Component)
        filters = []
        if component_type is not None:
            filters.append(Component.type == component_type)
        if cell_id is not None:
            filters.append(Component.cell_id == cell_id)
        if is_active is not None:
            filters.append(Component.is_active == is_active)
        if filters:
            stmt = stmt.where(and_(*filters))
        stmt = stmt.order_by(Component.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete_component(self, component: Component) -> None:
        await self._session.delete(component)
        await self._session.commit()

    # ── History ──────────────────────────────────────────────────────────────

    async def save_history(self, history: ComponentAssignmentHistory) -> ComponentAssignmentHistory:
        self._session.add(history)
        await self._session.commit()
        await self._session.refresh(history)
        return history

    async def find_history_by_component(self, component_id: int) -> list[ComponentAssignmentHistory]:
        result = await self._session.execute(
            select(ComponentAssignmentHistory)
            .where(ComponentAssignmentHistory.component_id == component_id)
            .order_by(ComponentAssignmentHistory.performed_at.desc())
        )
        return list(result.scalars().all())
