from typing import Protocol
from cell_management.domain.model.aggregates.Component import Component, ComponentType


class ComponentRepository(Protocol):

    async def save_component(self, component: Component) -> Component:
        """Persist a component and return it."""
        ...
    async def find_component_by_id(self, component_id: int) -> Component | None:
        """Find a component by its id."""
        ...
    async def find_all_components(
        self,
        component_type: ComponentType | None = None,
        cell_id: int | None = None,
        is_active: bool | None = None,
        visible_only: bool = True,
    ) -> list[Component]:
        """List components filtered by type, cell, active status and visibility."""
        ...
    async def find_by_serial_code(self, serial_code: str) -> Component | None:
        """Find a component by its serial code."""
        ...
    async def exists_by_serial_code(self, serial_code: str) -> bool:
        """Tell whether a component with this serial code exists."""
        ...
    async def release_components_of_cell(self, cell_id: int) -> list[Component]:
        """Release every component assigned to a cell and return them."""
        ...
    async def delete_component(self, component: Component) -> None:
        """Delete a component."""
        ...
