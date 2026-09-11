from cell_management.domain.model.aggregates.Cell import Cell
from cell_management.domain.model.queries.CellQueries import (
    GetCellByIdQuery,
    GetAllCellsQuery,
)
from cell_management.domain.repositories.CellRepository import CellRepository


class CellQueryServiceImpl:

    def __init__(self, repository: CellRepository):
        self._repository = repository

    async def get_cell_by_id(self, query: GetCellByIdQuery) -> Cell | None:
        return await self._repository.find_by_id(query.cell_id)

    async def get_all_cells(self, query: GetAllCellsQuery) -> list[Cell]:
        return await self._repository.find_all(is_active=query.is_active)
