import re

from sqlalchemy import String, Boolean, SmallInteger, text
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.persistence.configuration.database_configuration import Base


CELL_NAME_PATTERN = re.compile(r"[A-Z][1-9][0-9]*")


class Cell(Base):
    """
    Aggregate Root: Celda electrica de la planta industrial.
    """
    __tablename__ = "cell"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    barcode_value: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"), nullable=False)

    @staticmethod
    def normalize_name(name: str) -> str:
        """Cell names are a letter followed by a number (A1, A2, ... A150, B1, ...); stored in uppercase."""
        normalized = name.strip().upper()
        if not CELL_NAME_PATTERN.fullmatch(normalized):
            raise ValueError("Cell name must be a letter followed by a number, e.g. A1, B12")
        return normalized

    def disable(self) -> None:
        if not self.is_active:
            raise ValueError("Cell is already disabled")
        self.is_active = False

    def generate_barcode(self) -> None:
        """Assigns the barcode value derived from the cell id; keeps the existing one if already generated."""
        if not self.is_active:
            raise ValueError("Cannot generate a barcode for a disabled cell")
        if self.barcode_value is None:
            self.barcode_value = f"CELL-{self.id:05d}"

    def update_info(self, name: str) -> None:
        self.name = name
