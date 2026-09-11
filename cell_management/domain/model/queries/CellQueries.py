from dataclasses import dataclass


@dataclass(frozen=True)
class GetCellByIdQuery:
    cell_id: int


@dataclass(frozen=True)
class GetAllCellsQuery:
    is_active: bool | None = None
