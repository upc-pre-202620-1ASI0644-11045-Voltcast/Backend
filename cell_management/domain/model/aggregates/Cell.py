from sqlalchemy import String, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from shared.domain.model.aggregates.base_entity import BaseEntity


class Cell(BaseEntity):
    """
    Aggregate Root: Celda electrica de la planta industrial.
    """
    __tablename__ = "cells"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    voltage: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def disable(self) -> None:
        if not self.is_active:
            raise ValueError("Cell is already disabled")
        self.is_active = False

    def enable(self) -> None:
        if self.is_active:
            raise ValueError("Cell is already active")
        self.is_active = True

    def update_info(self, name: str | None = None, voltage: float | None = None) -> None:
        if name is not None:
            self.name = name
        if voltage is not None:
            self.voltage = voltage
