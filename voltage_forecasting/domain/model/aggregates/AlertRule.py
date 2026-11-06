from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, TIMESTAMP, text
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.persistence.configuration.column_types import SmallInt
from shared.infrastructure.persistence.configuration.database_configuration import Base


# Range of the limit the Supervisor can set (V), as the plant defines it: above 3.35 and up to 3.45.
MIN_MAX_VOLTAGE = 3.35  # exclusive
MAX_MAX_VOLTAGE = 3.45  # inclusive


class AlertRule(Base):
    """
    Aggregate Root: Voltaje máximo permitido (US007-E02). Sin celda es el umbral general; con celda
    reemplaza al general para esa celda. Solo hay una regla activa por alcance.
    """
    __tablename__ = "alert_rule"

    id: Mapped[int] = mapped_column(SmallInt, primary_key=True, autoincrement=True)
    cell_id: Mapped[int | None] = mapped_column(
        SmallInt, ForeignKey("cell.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True
    )
    max_voltage: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    @staticmethod
    def validate_max_voltage(max_voltage: float) -> None:
        if not MIN_MAX_VOLTAGE < max_voltage <= MAX_MAX_VOLTAGE:
            raise ValueError(f"Maximum voltage must be above {MIN_MAX_VOLTAGE} V and at most {MAX_MAX_VOLTAGE} V")
