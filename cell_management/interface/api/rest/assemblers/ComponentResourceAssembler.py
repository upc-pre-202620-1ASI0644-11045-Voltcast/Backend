from cell_management.domain.model.aggregates.Component import Component, ComponentType
from cell_management.domain.model.commands.ComponentCommands import (
    CreateComponentCommand,
    UpdateComponentCommand,
    DisableComponentCommand,
    ReactivateComponentCommand,
    HideComponentCommand,
    AssignComponentCommand,
    SwapComponentsCommand,
)
from cell_management.domain.model.queries.ComponentQueries import (
    GetComponentByIdQuery,
    GetAllComponentsQuery,
)
from cell_management.interface.api.rest.resources.ComponentResource import (
    ComponentRequest,
    ComponentUpdateRequest,
    ComponentAssignRequest,
    ComponentSwapRequest,
    ComponentResponse,
)


class ComponentResourceAssembler:

    @staticmethod
    def to_create_command(request: ComponentRequest) -> CreateComponentCommand:
        return CreateComponentCommand(
            type=ComponentType[request.type],
            serial_code=request.serial_code,
            cell_id=request.cell_id,
        )

    @staticmethod
    def to_update_command(component_id: int, request: ComponentUpdateRequest) -> UpdateComponentCommand:
        return UpdateComponentCommand(
            component_id=component_id,
            serial_code=request.serial_code,
            type=ComponentType[request.type] if request.type else None,
        )

    @staticmethod
    def to_disable_command(component_id: int) -> DisableComponentCommand:
        return DisableComponentCommand(component_id=component_id)

    @staticmethod
    def to_reactivate_command(component_id: int) -> ReactivateComponentCommand:
        return ReactivateComponentCommand(component_id=component_id)

    @staticmethod
    def to_hide_command(component_id: int) -> HideComponentCommand:
        return HideComponentCommand(component_id=component_id)

    @staticmethod
    def to_assign_command(component_id: int, request: ComponentAssignRequest) -> AssignComponentCommand:
        return AssignComponentCommand(component_id=component_id, cell_id=request.cell_id)

    @staticmethod
    def to_swap_command(request: ComponentSwapRequest) -> SwapComponentsCommand:
        return SwapComponentsCommand(
            component_a_id=request.component_a_id,
            component_b_id=request.component_b_id,
        )

    @staticmethod
    def to_get_by_id_query(component_id: int) -> GetComponentByIdQuery:
        return GetComponentByIdQuery(component_id=component_id)

    @staticmethod
    def to_get_all_query(
        component_type: str | None = None,
        cell_id: int | None = None,
        is_active: bool | None = None,
    ) -> GetAllComponentsQuery:
        return GetAllComponentsQuery(
            component_type=ComponentType[component_type] if component_type else None,
            cell_id=cell_id,
            is_active=is_active,
        )

    @staticmethod
    def to_response(component: Component) -> ComponentResponse:
        return ComponentResponse(
            id=component.id,
            type=ComponentType(component.type).name,
            serial_code=component.serial_code,
            is_active=component.is_active,
            cell_id=component.cell_id,
        )
