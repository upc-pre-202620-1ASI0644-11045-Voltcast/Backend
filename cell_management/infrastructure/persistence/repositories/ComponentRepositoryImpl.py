from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from cell_management.domain.model.aggregates.Component import Component, ComponentType


class ComponentRepositoryImpl:

    def __init__(self, session: AsyncSession):
        self._session = session

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
        component_type: ComponentType | None = None,
        cell_id: int | None = None,
        is_active: bool | None = None,
        visible_only: bool = True,
    ) -> list[Component]:
        stmt = select(Component)
        filters = []
        if visible_only:
            filters.append(Component.is_visible.is_(True))
        if component_type is not None:
            filters.append(Component.type == int(component_type))
        if cell_id is not None:
            filters.append(Component.cell_id == cell_id)
        if is_active is not None:
            filters.append(Component.is_active == is_active)
        if filters:
            stmt = stmt.where(and_(*filters))
        stmt = stmt.order_by(Component.id.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_serial_code(self, serial_code: str) -> Component | None:
        result = await self._session.execute(select(Component).where(Component.serial_code == serial_code))
        return result.scalar_one_or_none()

    async def exists_by_serial_code(self, serial_code: str) -> bool:
        result = await self._session.execute(
            select(Component.id).where(Component.serial_code == serial_code)
        )
        return result.scalar_one_or_none() is not None

    async def release_components_of_cell(self, cell_id: int) -> list[Component]:
        """
        Unassigns every component of the cell without committing, so the caller can
        persist it atomically together with other changes of the same session.
        """
        components = await self.find_all_components(cell_id=cell_id)
        for component in components:
            component.unassign()
        return components

    async def delete_component(self, component: Component) -> None:
        await self._session.delete(component)
        await self._session.commit()
