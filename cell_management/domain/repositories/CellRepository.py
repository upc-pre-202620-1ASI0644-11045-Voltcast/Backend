from typing import Protocol
from cell_management.domain.model.aggregates.Cell import Cell


class CellRepository(Protocol):

    async def save(self, cell: Cell) -> Cell:
        """Persist a cell and return it."""
        ...
    async def find_by_id(self, cell_id: int) -> Cell | None:
        """Find a cell by its id."""
        ...
    async def find_by_name(self, name: str) -> Cell | None:
        """Find a cell by its name."""
        ...
    async def find_all(self, is_active: bool | None = None, visible_only: bool = True) -> list[Cell]:
        """List cells, optionally filtered by active status and visibility."""
        ...
    async def delete(self, cell: Cell) -> None:
        """Delete a cell."""
        ...
    async def exists_by_name(self, name: str) -> bool:
        """Tell whether a cell with this name exists."""
        ...
