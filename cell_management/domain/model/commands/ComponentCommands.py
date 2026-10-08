from dataclasses import dataclass

from cell_management.domain.model.aggregates.Component import ComponentType


@dataclass(frozen=True)
class CreateComponentCommand:
    type: ComponentType
    serial_code: str
    cell_id: int | None = None


@dataclass(frozen=True)
class UpdateComponentCommand:
    component_id: int
    serial_code: str | None = None
    type: ComponentType | None = None


@dataclass(frozen=True)
class DisableComponentCommand:
    component_id: int


@dataclass(frozen=True)
class AssignComponentCommand:
    component_id: int
    cell_id: int


@dataclass(frozen=True)
class SwapComponentsCommand:
    component_a_id: int
    component_b_id: int
