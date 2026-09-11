from typing import Literal
from sqlalchemy import String, Boolean, Integer, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from shared.domain.model.aggregates.base_entity import BaseEntity, utc_now

ComponentType = Literal["CATHODE", "ANODE"]


class Component(BaseEntity):
    """
    Componente (cátodo o ánodo) asignado a una celda eléctrica.
    """
    __tablename__ = "components"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)  # CATHODE | ANODE
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cell_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("cells.id", ondelete="SET NULL"), nullable=True, index=True
    )

    def assign_to(self, cell_id: int) -> None:
        if not self.is_active:
            raise ValueError("Cannot assign a disabled component")
        self.cell_id = cell_id

    def unassign(self) -> None:
        self.cell_id = None

    def disable(self) -> None:
        if not self.is_active:
            raise ValueError("Component is already disabled")
        self.is_active = False
        self.cell_id = None

    def enable(self) -> None:
        if self.is_active:
            raise ValueError("Component is already active")
        self.is_active = True

    def update_info(self, name: str | None = None, component_type: str | None = None) -> None:
        if name is not None:
            self.name = name
        if component_type is not None:
            if component_type not in ("CATHODE", "ANODE"):
                raise ValueError("Type must be CATHODE or ANODE")
            self.type = component_type


class ComponentAssignmentHistory(BaseEntity):
    """
    Historial de asignaciones, intercambios y deshabilitaciones de componentes.
    """
    __tablename__ = "component_assignment_history"

    component_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("components.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_cell_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("cells.id", ondelete="SET NULL"), nullable=True
    )
    to_cell_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("cells.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # ASSIGNED | SWAPPED | UNASSIGNED | DISABLED
    performed_at = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
