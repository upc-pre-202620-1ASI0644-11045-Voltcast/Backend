from cell_management.domain.model.aggregates.Component import Component
from cell_management.domain.model.commands.ComponentCommands import (
    CreateComponentCommand,
    UpdateComponentCommand,
    DisableComponentCommand,
    ReactivateComponentCommand,
    HideComponentCommand,
    AssignComponentCommand,
    SwapComponentsCommand,
)
from cell_management.domain.repositories.CellRepository import CellRepository
from cell_management.domain.repositories.ComponentRepository import ComponentRepository


class ComponentCommandServiceImpl:

    def __init__(
        self,
        component_repository: ComponentRepository,
        cell_repository: CellRepository,
    ):
        self._component_repo = component_repository
        self._cell_repo = cell_repository

    async def create_component(self, command: CreateComponentCommand) -> Component:
        existing = await self._component_repo.find_by_serial_code(command.serial_code)
        if existing and existing.is_active and existing.is_visible:
            raise ValueError(f"Component with serial code '{command.serial_code}' already exists")
        if command.cell_id is not None:
            await self._get_visible_cell_or_raise(command.cell_id)
        if existing:
            # Disabled or removed from view: the same component comes back instead of a duplicate.
            existing.revive(command.type, command.cell_id)
            component = existing
        else:
            component = Component(
                type=int(command.type),
                serial_code=command.serial_code,
                is_active=True,
                is_visible=True,
                cell_id=command.cell_id,
            )
        saved = await self._component_repo.save_component(component)
        await self._refresh_cells(saved.cell_id)
        return saved

    async def update_component(self, command: UpdateComponentCommand) -> Component:
        component = await self._get_or_raise(command.component_id)
        if (
            command.serial_code is not None
            and command.serial_code != component.serial_code
            and await self._component_repo.exists_by_serial_code(command.serial_code)
        ):
            raise ValueError(f"Component with serial code '{command.serial_code}' already exists")
        component.update_info(serial_code=command.serial_code, component_type=command.type)
        saved = await self._component_repo.save_component(component)
        # A new type can complete or break the pair of its cell.
        await self._refresh_cells(saved.cell_id)
        return saved

    async def disable_component(self, command: DisableComponentCommand) -> Component:
        component = await self._get_or_raise(command.component_id)
        component.disable()
        return await self._component_repo.save_component(component)

    async def reactivate_component(self, command: ReactivateComponentCommand) -> Component:
        component = await self._get_or_raise(command.component_id)
        component.reactivate()
        return await self._component_repo.save_component(component)

    async def hide_component(self, command: HideComponentCommand) -> Component:
        component = await self._get_or_raise(command.component_id)
        component.hide()
        return await self._component_repo.save_component(component)

    async def assign_component(self, command: AssignComponentCommand) -> Component:
        component = await self._get_or_raise(command.component_id)
        await self._get_visible_cell_or_raise(command.cell_id)
        previous_cell_id = component.cell_id
        component.assign_to(command.cell_id)
        saved = await self._component_repo.save_component(component)
        await self._refresh_cells(previous_cell_id, command.cell_id)
        return saved

    async def swap_components(self, command: SwapComponentsCommand) -> tuple[Component, Component]:
        comp_a = await self._get_or_raise(command.component_a_id)
        comp_b = await self._get_or_raise(command.component_b_id)

        if comp_a.type != comp_b.type:
            raise ValueError("Can only swap components of the same type (CATHODE with CATHODE, ANODE with ANODE)")
        if comp_a.cell_id is None or comp_b.cell_id is None:
            raise ValueError("Both components must be assigned to a cell to be swapped")
        if comp_a.cell_id == comp_b.cell_id:
            raise ValueError("Components belong to the same cell")

        cell_a_id, cell_b_id = comp_a.cell_id, comp_b.cell_id
        comp_a.assign_to(cell_b_id)
        comp_b.assign_to(cell_a_id)

        # Both components are tracked by the same session: a single commit persists the swap atomically.
        saved_a = await self._component_repo.save_component(comp_a)
        await self._refresh_cells(cell_a_id, cell_b_id)
        return saved_a, comp_b

    async def _refresh_cells(self, *cell_ids: int | None) -> None:
        """Recomputes the status of the given cells from the components they now have."""
        for cell_id in {cell_id for cell_id in cell_ids if cell_id is not None}:
            cell = await self._cell_repo.find_by_id(cell_id)
            if cell:
                assigned = await self._component_repo.find_all_components(cell_id=cell_id, is_active=True)
                cell.refresh_status({component.type for component in assigned})
                await self._cell_repo.save(cell)

    async def _get_visible_cell_or_raise(self, cell_id: int):
        """Any cell can receive components (that is what activates it), except one removed from view."""
        cell = await self._cell_repo.find_by_id(cell_id)
        if not cell or not cell.is_visible:
            raise ValueError(f"Cell not found: {cell_id}")
        return cell

    async def _get_or_raise(self, component_id: int) -> Component:
        component = await self._component_repo.find_component_by_id(component_id)
        if not component:
            raise ValueError(f"Component not found: {component_id}")
        return component
