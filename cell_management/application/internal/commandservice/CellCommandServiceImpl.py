from cell_management.domain.model.aggregates.Cell import Cell
from cell_management.domain.model.commands.CellCommands import (
    CreateCellCommand,
    UpdateCellCommand,
    ReleaseCellComponentsCommand,
    HideCellCommand,
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
        name = Cell.normalize_name(command.name)
        existing = await self._repository.find_by_name(name)
        if existing:
            if existing.is_visible:
                raise ValueError(f"Cell '{name}' already exists")
            # Removed from view earlier: the same cell comes back (inactive, it has no components).
            existing.show()
            return await self._repository.save(existing)
        return await self._repository.save(Cell(name=name, is_active=False, is_visible=True))

    async def update_cell(self, command: UpdateCellCommand) -> Cell:
        cell = await self._get_or_raise(command.cell_id)
        name = Cell.normalize_name(command.name)
        if name != cell.name and await self._repository.exists_by_name(name):
            raise ValueError(f"Cell '{name}' already exists")
        cell.update_info(name=name)
        return await self._repository.save(cell)

    async def release_components(self, command: ReleaseCellComponentsCommand) -> Cell:
        """Frees the cell's cathode and anode; without them the cell is inactive."""
        cell = await self._get_or_raise(command.cell_id)
        await self._component_repo.release_components_of_cell(cell.id)
        cell.refresh_status(set())
        # Same session: this commit persists the released components and the cell status atomically.
        return await self._repository.save(cell)

    async def hide_cell(self, command: HideCellCommand) -> Cell:
        """Removes the cell from view. Its components have to be released first."""
        cell = await self._get_or_raise(command.cell_id)
        if await self._component_repo.find_all_components(cell_id=cell.id):
            raise ValueError("Cell has assigned cathodes/anodes; release them before removing it")
        cell.hide()
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
