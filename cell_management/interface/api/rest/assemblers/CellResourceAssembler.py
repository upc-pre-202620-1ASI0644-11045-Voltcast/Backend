from cell_management.domain.model.aggregates.Cell import Cell
from cell_management.domain.model.commands.CellCommands import (
    CreateCellCommand,
    UpdateCellCommand,
    DisableCellCommand,
)
from cell_management.domain.model.queries.CellQueries import (
    GetCellByIdQuery,
    GetAllCellsQuery,
)
from cell_management.interface.api.rest.resources.CellResource import (
    CellRequest,
    CellUpdateRequest,
    CellResponse,
)


class CellResourceAssembler:

    @staticmethod
    def to_create_command(request: CellRequest) -> CreateCellCommand:
        return CreateCellCommand(name=request.name, voltage=request.voltage)

    @staticmethod
    def to_update_command(cell_id: int, request: CellUpdateRequest) -> UpdateCellCommand:
        return UpdateCellCommand(cell_id=cell_id, name=request.name, voltage=request.voltage)

    @staticmethod
    def to_disable_command(cell_id: int) -> DisableCellCommand:
        return DisableCellCommand(cell_id=cell_id)

    @staticmethod
    def to_get_by_id_query(cell_id: int) -> GetCellByIdQuery:
        return GetCellByIdQuery(cell_id=cell_id)

    @staticmethod
    def to_get_all_query(is_active: bool | None = None) -> GetAllCellsQuery:
        return GetAllCellsQuery(is_active=is_active)

    @staticmethod
    def to_response(cell: Cell) -> CellResponse:
        return CellResponse(
            id=cell.id,
            name=cell.name,
            voltage=cell.voltage,
            is_active=cell.is_active,
            created_at=cell.created_at,
            updated_at=cell.updated_at,
        )
