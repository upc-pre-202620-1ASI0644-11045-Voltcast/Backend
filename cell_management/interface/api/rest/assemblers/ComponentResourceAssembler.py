from cell_management.domain.model.aggregates.Component import Component, ComponentAssignmentHistory
from cell_management.domain.model.commands.ComponentCommands import (
    CreateComponentCommand,
    UpdateComponentCommand,
    DisableComponentCommand,
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
    AssignmentHistoryResponse,
)


class ComponentResourceAssembler:

    @staticmethod
    def to_create_command(request: ComponentRequest) -> CreateComponentCommand:
        return CreateComponentCommand(
            name=request.name,
            type=request.type,
            cell_id=request.cell_id,
        )

    @staticmethod
    def to_update_command(component_id: int, request: ComponentUpdateRequest) -> UpdateComponentCommand:
        return UpdateComponentCommand(
            component_id=component_id,
            name=request.name,
            type=request.type,
        )

    @staticmethod
    def to_disable_command(component_id: int) -> DisableComponentCommand:
        return DisableComponentCommand(component_id=component_id)

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
        return GetAllComponentsQuery(component_type=component_type, cell_id=cell_id, is_active=is_active)

    @staticmethod
    def to_response(component: Component) -> ComponentResponse:
        return ComponentResponse(
            id=component.id,
            name=component.name,
            type=component.type,
            is_active=component.is_active,
            cell_id=component.cell_id,
            created_at=component.created_at,
            updated_at=component.updated_at,
        )

    @staticmethod
    def to_history_response(history: ComponentAssignmentHistory) -> AssignmentHistoryResponse:
        return AssignmentHistoryResponse(
            id=history.id,
            component_id=history.component_id,
            from_cell_id=history.from_cell_id,
            to_cell_id=history.to_cell_id,
            action=history.action,
            performed_at=history.performed_at,
            created_at=history.created_at,
        )
