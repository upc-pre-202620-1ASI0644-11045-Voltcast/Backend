from cell_management.domain.model.aggregates.Cell import Cell
from cell_management.domain.model.commands.CellCommands import (
    CreateCellCommand,
    UpdateCellCommand,
    ReleaseCellComponentsCommand,
    HideCellCommand,
    GenerateCellBarcodeCommand,
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
        return CreateCellCommand(name=request.name)

    @staticmethod
    def to_update_command(cell_id: int, request: CellUpdateRequest) -> UpdateCellCommand:
        return UpdateCellCommand(cell_id=cell_id, name=request.name)

    @staticmethod
    def to_release_command(cell_id: int) -> ReleaseCellComponentsCommand:
        return ReleaseCellComponentsCommand(cell_id=cell_id)

    @staticmethod
    def to_hide_command(cell_id: int) -> HideCellCommand:
        return HideCellCommand(cell_id=cell_id)

    @staticmethod
    def to_generate_barcode_command(cell_id: int) -> GenerateCellBarcodeCommand:
        return GenerateCellBarcodeCommand(cell_id=cell_id)

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
            barcode_value=cell.barcode_value,
            is_active=cell.is_active,
        )
