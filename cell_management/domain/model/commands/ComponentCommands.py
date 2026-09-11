from dataclasses import dataclass


@dataclass(frozen=True)
class CreateComponentCommand:
    name: str
    type: str  # CATHODE | ANODE
    cell_id: int | None = None


@dataclass(frozen=True)
class UpdateComponentCommand:
    component_id: int
    name: str | None = None
    type: str | None = None


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
