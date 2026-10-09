from enum import IntEnum

from sqlalchemy import String, Boolean, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.persistence.configuration.column_types import SmallInt, TinyInt1
from shared.infrastructure.persistence.configuration.database_configuration import Base


class ComponentType(IntEnum):
    CATHODE = 0
    ANODE = 1


class Component(Base):
    """
    Componente (cátodo o ánodo) que puede estar asignado a una celda eléctrica.
    """
    __tablename__ = "component"

    id: Mapped[int] = mapped_column(SmallInt, primary_key=True, autoincrement=True)
    type: Mapped[int] = mapped_column(TinyInt1, nullable=False)  # ComponentType: 0 = cátodo, 1 = ánodo
    serial_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"), nullable=False)
    cell_id: Mapped[int | None] = mapped_column(SmallInt, ForeignKey("cell.id"), nullable=True)

    def assign_to(self, cell_id: int) -> None:
        if not self.is_active:
            raise ValueError("Cannot assign a disabled component")
        self.cell_id = cell_id

    def unassign(self) -> None:
        self.cell_id = None

    def disable(self) -> None:
        if not self.is_active:
            raise ValueError("Component is already disabled")
        if self.cell_id is not None:
            raise ValueError("Component is in use: it is assigned to a cell")
        self.is_active = False

    def update_info(self, serial_code: str | None = None, component_type: ComponentType | None = None) -> None:
        if serial_code is not None:
            self.serial_code = serial_code
        if component_type is not None:
            self.type = int(component_type)
