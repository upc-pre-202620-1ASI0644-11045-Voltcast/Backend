from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cell_management.domain.model.aggregates.Cell import Cell


class CellRepositoryImpl:

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, cell: Cell) -> Cell:
        """Persist a cell and return it refreshed."""
        self._session.add(cell)
        await self._session.commit()
        await self._session.refresh(cell)
        return cell

    async def find_by_id(self, cell_id: int) -> Cell | None:
        """Find a cell by its id."""
        result = await self._session.execute(select(Cell).where(Cell.id == cell_id))
        return result.scalar_one_or_none()

    async def find_by_name(self, name: str) -> Cell | None:
        """Find a cell by its name."""
        result = await self._session.execute(select(Cell).where(Cell.name == name))
        return result.scalar_one_or_none()

    async def find_all(self, is_active: bool | None = None, visible_only: bool = True) -> list[Cell]:
        """List cells, newest first, optionally filtered by active status and visibility."""
        stmt = select(Cell)
        if visible_only:
            stmt = stmt.where(Cell.is_visible.is_(True))
        if is_active is not None:
            stmt = stmt.where(Cell.is_active == is_active)
        stmt = stmt.order_by(Cell.id.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, cell: Cell) -> None:
        """Delete a cell and commit."""
        await self._session.delete(cell)
        await self._session.commit()

    async def exists_by_name(self, name: str) -> bool:
        """Tell whether a cell with this name exists."""
        result = await self._session.execute(select(Cell.id).where(Cell.name == name))
        return result.scalar_one_or_none() is not None
