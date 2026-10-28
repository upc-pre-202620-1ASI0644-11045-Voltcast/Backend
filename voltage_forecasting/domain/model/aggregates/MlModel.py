from sqlalchemy import String, Boolean, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.persistence.configuration.column_types import SmallInt
from shared.infrastructure.persistence.configuration.database_configuration import Base

MODEL_NAME = "bi_lstm"


class MlModel(Base):
    """
    Aggregate Root: Versión de un modelo predictivo. El artefacto vive en Blob Storage (artifact_path);
    solo una versión está activa y es la que alimenta los pronósticos.
    """
    __tablename__ = "ml_model"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_model_version"),)

    id: Mapped[int] = mapped_column(SmallInt, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(30), nullable=False)
    artifact_path: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"), nullable=False)
