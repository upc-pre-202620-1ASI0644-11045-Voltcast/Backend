from dataclasses import dataclass

from cell_management.domain.model.aggregates.Component import ComponentType


@dataclass(frozen=True)
class GetComponentByIdQuery:
    component_id: int


@dataclass(frozen=True)
class GetAllComponentsQuery:
    component_type: ComponentType | None = None
    cell_id: int | None = None
    is_active: bool | None = None
