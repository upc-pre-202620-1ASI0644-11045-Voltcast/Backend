from dataclasses import dataclass


@dataclass(frozen=True)
class CreateCellCommand:
    name: str
    voltage: float


@dataclass(frozen=True)
class UpdateCellCommand:
    cell_id: int
    name: str | None = None
    voltage: float | None = None


@dataclass(frozen=True)
class DisableCellCommand:
    cell_id: int
