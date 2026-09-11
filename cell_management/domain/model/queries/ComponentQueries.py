from dataclasses import dataclass


@dataclass(frozen=True)
class GetComponentByIdQuery:
    component_id: int


@dataclass(frozen=True)
class GetAllComponentsQuery:
    component_type: str | None = None
    cell_id: int | None = None
    is_active: bool | None = None
