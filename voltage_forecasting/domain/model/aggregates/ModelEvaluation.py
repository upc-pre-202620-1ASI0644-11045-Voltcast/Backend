from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, Integer, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.persistence.configuration.column_types import SmallInt
from shared.infrastructure.persistence.configuration.database_configuration import Base


class ModelEvaluation(Base):
    """Aggregate Root: Evaluación de una versión del modelo contra los datos reales de un dataset (US006)."""
    __tablename__ = "model_evaluation"

    id: Mapped[int] = mapped_column(SmallInt, primary_key=True, autoincrement=True)
    model_id: Mapped[int] = mapped_column(
        SmallInt, ForeignKey("ml_model.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    dataset_id: Mapped[int] = mapped_column(
        SmallInt, ForeignKey("uploaded_dataset.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )


class ModelEvaluationResult(Base):
    """Par pronóstico/real de una celda y un día dentro de una evaluación; las métricas se calculan sobre estas filas."""
    __tablename__ = "model_evaluation_result"
    __table_args__ = (Index("idx_simres_sim_cell", "model_evaluation_id", "cell_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_evaluation_id: Mapped[int] = mapped_column(
        SmallInt, ForeignKey("model_evaluation.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    cell_id: Mapped[int] = mapped_column(
        SmallInt, ForeignKey("cell.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    prediction_date: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    predicted_value: Mapped[float] = mapped_column(Float, nullable=False)
    real_value: Mapped[float] = mapped_column(Float, nullable=False)
