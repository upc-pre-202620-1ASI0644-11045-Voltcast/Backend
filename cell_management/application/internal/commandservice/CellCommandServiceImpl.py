from cell_management.domain.model.aggregates.Cell import Cell
from cell_management.domain.model.commands.CellCommands import (
    CreateCellCommand,
    UpdateCellCommand,
    DisableCellCommand,
)
from cell_management.domain.repositories.CellRepository import CellRepository


class CellCommandServiceImpl:

    def __init__(self, repository: CellRepository):
        self._repository = repository

    async def create_cell(self, command: CreateCellCommand) -> Cell:
        if await self._repository.exists_by_name(command.name):
            raise ValueError(f"Cell '{command.name}' already exists")
        cell = Cell(name=command.name, voltage=command.voltage, is_active=True)
        return await self._repository.save(cell)

    async def update_cell(self, command: UpdateCellCommand) -> Cell:
        cell = await self._get_or_raise(command.cell_id)
        if command.name and command.name != cell.name:
            if await self._repository.exists_by_name(command.name):
                raise ValueError(f"Cell '{command.name}' already exists")
        cell.update_info(name=command.name, voltage=command.voltage)
        return await self._repository.save(cell)

    async def disable_cell(self, command: DisableCellCommand) -> Cell:
        cell = await self._get_or_raise(command.cell_id)
        cell.disable()
        return await self._repository.save(cell)

    async def _get_or_raise(self, cell_id: int) -> Cell:
        cell = await self._repository.find_by_id(cell_id)
        if not cell:
            raise ValueError(f"Cell not found: {cell_id}")
        return cell
