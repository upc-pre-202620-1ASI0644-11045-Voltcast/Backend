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
        """Build the create-cell command from the request."""
        return CreateCellCommand(name=request.name)

    @staticmethod
    def to_update_command(cell_id: int, request: CellUpdateRequest) -> UpdateCellCommand:
        """Build the update-cell command from the request."""
        return UpdateCellCommand(cell_id=cell_id, name=request.name)

    @staticmethod
    def to_release_command(cell_id: int) -> ReleaseCellComponentsCommand:
        """Build the command that releases the components of a cell."""
        return ReleaseCellComponentsCommand(cell_id=cell_id)

    @staticmethod
    def to_hide_command(cell_id: int) -> HideCellCommand:
        """Build the hide-cell command."""
        return HideCellCommand(cell_id=cell_id)

    @staticmethod
    def to_generate_barcode_command(cell_id: int) -> GenerateCellBarcodeCommand:
        """Build the generate-barcode command."""
        return GenerateCellBarcodeCommand(cell_id=cell_id)

    @staticmethod
    def to_get_by_id_query(cell_id: int) -> GetCellByIdQuery:
        """Build the query for one cell."""
        return GetCellByIdQuery(cell_id=cell_id)

    @staticmethod
    def to_get_all_query(is_active: bool | None = None) -> GetAllCellsQuery:
        """Build the query for the list of cells."""
        return GetAllCellsQuery(is_active=is_active)

    @staticmethod
    def to_response(cell: Cell) -> CellResponse:
        """Map a cell to its API response."""
        return CellResponse(
            id=cell.id,
            name=cell.name,
            barcode_value=cell.barcode_value,
            is_active=cell.is_active,
        )
