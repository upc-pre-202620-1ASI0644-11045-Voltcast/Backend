from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, Integer, TIMESTAMP, text
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.persistence.configuration.column_types import SmallInt
from shared.infrastructure.persistence.configuration.database_configuration import Base


class Prediction(Base):
    """Pronóstico de voltaje de una celda para un día, generado por una versión del modelo (lo escribe el Job)."""
    __tablename__ = "prediction"
    __table_args__ = (
        Index("idx_fc_date", "prediction_date"),
        Index("idx_fc_model_cell_date", "model_id", "cell_id", "prediction_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_id: Mapped[int] = mapped_column(
        SmallInt, ForeignKey("ml_model.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    cell_id: Mapped[int] = mapped_column(
        SmallInt, ForeignKey("cell.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    prediction_date: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    predicted_voltage: Mapped[float] = mapped_column(Float, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
