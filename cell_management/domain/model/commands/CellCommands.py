from dataclasses import dataclass


@dataclass(frozen=True)
class CreateCellCommand:
    name: str


@dataclass(frozen=True)
class UpdateCellCommand:
    cell_id: int
    name: str


@dataclass(frozen=True)
class DisableCellCommand:
    cell_id: int
    release_components: bool = False
