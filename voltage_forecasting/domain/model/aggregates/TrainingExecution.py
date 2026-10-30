from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Float, ForeignKey, TIMESTAMP, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.persistence.configuration.column_types import SmallInt, TinyInt
from shared.infrastructure.persistence.configuration.database_configuration import Base


class TrainingStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class TrainingExecution(Base):
    """
    Aggregate Root: Ejecución de entrenamiento de un modelo sobre un dataset limpio (la lleva a cabo el Job).
    Mientras hay una en 'running' el modelo está en reentrenamiento (US005-E02, US006-E02).
    """
    __tablename__ = "training_execution"

    id: Mapped[int] = mapped_column(SmallInt, primary_key=True, autoincrement=True)
    model_id: Mapped[int] = mapped_column(
        SmallInt, ForeignKey("ml_model.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    dataset_id: Mapped[int] = mapped_column(
        SmallInt, ForeignKey("uploaded_dataset.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    status: Mapped[TrainingStatus] = mapped_column(
        SAEnum(TrainingStatus, values_callable=lambda enum: [member.value for member in enum]),
        nullable=False,
        default=TrainingStatus.RUNNING,
        server_default=TrainingStatus.RUNNING.value,
    )
    rmse: Mapped[float | None] = mapped_column(Float, nullable=True)
    mae: Mapped[float | None] = mapped_column(Float, nullable=True)
    mape: Mapped[float | None] = mapped_column(Float, nullable=True)
    r2: Mapped[float | None] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    # ERD: NOT NULL with a NULL default, which no running row can satisfy; it has to allow NULL.
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)
    # ERD: NOT NULL, but its foreign key is SET NULL (MySQL rejects that); it has to allow NULL.
    executed_by: Mapped[int | None] = mapped_column(
        TinyInt, ForeignKey("user.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True
    )

    def mark_failed(self) -> None:
        self.status = TrainingStatus.FAILED
        self.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
