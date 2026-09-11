from cell_management.domain.model.aggregates.Component import Component, ComponentAssignmentHistory
from cell_management.domain.model.commands.ComponentCommands import (
    CreateComponentCommand,
    UpdateComponentCommand,
    DisableComponentCommand,
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
        if command.type not in ("CATHODE", "ANODE"):
            raise ValueError("Type must be CATHODE or ANODE")
        if command.cell_id is not None:
            cell = await self._cell_repo.find_by_id(command.cell_id)
            if not cell:
                raise ValueError(f"Cell not found: {command.cell_id}")
        component = Component(
            name=command.name,
            type=command.type,
            is_active=True,
            cell_id=command.cell_id,
        )
        saved = await self._component_repo.save_component(component)
        if command.cell_id is not None:
            await self._log_history(saved.id, None, command.cell_id, "ASSIGNED")
        return saved

    async def update_component(self, command: UpdateComponentCommand) -> Component:
        component = await self._get_or_raise(command.component_id)
        component.update_info(name=command.name, component_type=command.type)
        return await self._component_repo.save_component(component)

    async def disable_component(self, command: DisableComponentCommand) -> Component:
        component = await self._get_or_raise(command.component_id)
        from_cell = component.cell_id
        component.disable()
        saved = await self._component_repo.save_component(component)
        await self._log_history(saved.id, from_cell, None, "DISABLED")
        return saved

    async def assign_component(self, command: AssignComponentCommand) -> Component:
        component = await self._get_or_raise(command.component_id)
        cell = await self._cell_repo.find_by_id(command.cell_id)
        if not cell:
            raise ValueError(f"Cell not found: {command.cell_id}")
        from_cell = component.cell_id
        component.assign_to(command.cell_id)
        saved = await self._component_repo.save_component(component)
        await self._log_history(saved.id, from_cell, command.cell_id, "ASSIGNED")
        return saved

    async def swap_components(self, command: SwapComponentsCommand) -> tuple[Component, Component]:
        comp_a = await self._get_or_raise(command.component_a_id)
        comp_b = await self._get_or_raise(command.component_b_id)

        if comp_a.type != comp_b.type:
            raise ValueError("Can only swap components of the same type (CATHODE with CATHODE, ANODE with ANODE)")

        cell_a_id = comp_a.cell_id
        cell_b_id = comp_b.cell_id

        comp_a.assign_to(cell_b_id)
        comp_b.assign_to(cell_a_id)

        saved_a = await self._component_repo.save_component(comp_a)
        saved_b = await self._component_repo.save_component(comp_b)

        await self._log_history(saved_a.id, cell_a_id, cell_b_id, "SWAPPED")
        await self._log_history(saved_b.id, cell_b_id, cell_a_id, "SWAPPED")

        return saved_a, saved_b

    async def _log_history(
        self,
        component_id: int,
        from_cell_id: int | None,
        to_cell_id: int | None,
        action: str,
    ) -> None:
        history = ComponentAssignmentHistory(
            component_id=component_id,
            from_cell_id=from_cell_id,
            to_cell_id=to_cell_id,
            action=action,
        )
        await self._component_repo.save_history(history)

    async def _get_or_raise(self, component_id: int) -> Component:
        component = await self._component_repo.find_component_by_id(component_id)
        if not component:
            raise ValueError(f"Component not found: {component_id}")
        return component
