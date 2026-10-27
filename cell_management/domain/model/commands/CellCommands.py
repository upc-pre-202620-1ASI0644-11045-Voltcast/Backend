from dataclasses import dataclass


@dataclass(frozen=True)
class CreateCellCommand:
    name: str


@dataclass(frozen=True)
class UpdateCellCommand:
    cell_id: int
    name: str


@dataclass(frozen=True)
class ReleaseCellComponentsCommand:
    cell_id: int


@dataclass(frozen=True)
class HideCellCommand:
    cell_id: int


@dataclass(frozen=True)
class GenerateCellBarcodeCommand:
    cell_id: int
