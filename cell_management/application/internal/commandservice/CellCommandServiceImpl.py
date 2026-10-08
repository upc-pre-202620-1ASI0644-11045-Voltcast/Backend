from cell_management.domain.model.aggregates.Cell import Cell
from cell_management.domain.model.commands.CellCommands import (
    CreateCellCommand,
    UpdateCellCommand,
    DisableCellCommand,
    GenerateCellBarcodeCommand,
)
from cell_management.domain.model.aggregates.Component import ComponentType
from cell_management.domain.repositories.CellRepository import CellRepository
from cell_management.domain.repositories.ComponentRepository import ComponentRepository


class CellCommandServiceImpl:

    def __init__(self, repository: CellRepository, component_repository: ComponentRepository):
        self._repository = repository
        self._component_repo = component_repository

    async def create_cell(self, command: CreateCellCommand) -> Cell:
        if await self._repository.exists_by_name(command.name):
            raise ValueError(f"Cell '{command.name}' already exists")
        cell = Cell(name=command.name, is_active=True)
        return await self._repository.save(cell)

    async def update_cell(self, command: UpdateCellCommand) -> Cell:
        cell = await self._get_or_raise(command.cell_id)
        if command.name != cell.name and await self._repository.exists_by_name(command.name):
            raise ValueError(f"Cell '{command.name}' already exists")
        cell.update_info(name=command.name)
        return await self._repository.save(cell)

    async def disable_cell(self, command: DisableCellCommand) -> Cell:
        cell = await self._get_or_raise(command.cell_id)
        assigned = await self._component_repo.find_all_components(cell_id=cell.id)
        if assigned and not command.release_components:
            raise ValueError(
                "Cell has assigned cathodes/anodes; release them first or disable with release_components=true"
            )
        await self._component_repo.release_components_of_cell(cell.id)
        cell.disable()
        # Same session: this commit persists the released components and the disabled cell atomically.
        return await self._repository.save(cell)

    async def generate_barcode(self, command: GenerateCellBarcodeCommand) -> Cell:
        cell = await self._get_or_raise(command.cell_id)
        components = await self._component_repo.find_all_components(cell_id=cell.id, is_active=True)
        assigned_types = {component.type for component in components}
        if assigned_types != {int(ComponentType.CATHODE), int(ComponentType.ANODE)}:
            raise ValueError("Cell must have an assigned cathode and anode to generate its barcode")
        cell.generate_barcode()
        return await self._repository.save(cell)

    async def _get_or_raise(self, cell_id: int) -> Cell:
        cell = await self._repository.find_by_id(cell_id)
        if not cell:
            raise ValueError(f"Cell not found: {cell_id}")
        return cell
