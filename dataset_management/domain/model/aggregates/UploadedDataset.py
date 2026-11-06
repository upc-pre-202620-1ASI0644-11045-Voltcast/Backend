from datetime import datetime
from enum import Enum
from pathlib import PurePath

from sqlalchemy import ForeignKey, String, Text, Integer, TIMESTAMP, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.persistence.configuration.column_types import SmallInt
from shared.infrastructure.persistence.configuration.database_configuration import Base

ALLOWED_EXTENSIONS = {".xlsx", ".xlsm", ".xls"}
MAX_UPLOAD_BYTES = 100 * 1024 * 1024


class DatasetStatus(str, Enum):
    RAW = "raw"
    CLEANING = "cleaning"
    AWAITING_CONFIRMATION = "awaiting_confirmation"  # a file that complements another one, waiting for the user to accept the merge
    READY = "ready"
    FAILED = "failed"


class UploadedDataset(Base):
    """
    Aggregate Root: Archivo histórico de voltajes cargado por el Ingeniero de Planta.
    Flujo de estado: raw -> cleaning -> ready | failed (lo avanza el Job de ETL).
    Un archivo que complementa a otro (base_dataset_id): raw -> cleaning -> awaiting_confirmation -> (confirma) raw -> cleaning -> ready | failed.
    """
    __tablename__ = "uploaded_dataset"

    id: Mapped[int] = mapped_column(SmallInt, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(255), nullable=False)
    upload_status: Mapped[DatasetStatus] = mapped_column(
        SAEnum(DatasetStatus, values_callable=lambda enum: [member.value for member in enum]),
        nullable=False,
        default=DatasetStatus.RAW,
        server_default=DatasetStatus.RAW.value,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    processed_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    processed_row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    base_dataset_id: Mapped[int | None] = mapped_column(
        SmallInt, ForeignKey("uploaded_dataset.id"), nullable=True
    )  # the dataset this file complements: its raw data is merged with this one before cleaning
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    @staticmethod
    def validate_upload(filename: str, content: bytes) -> str:
        """Returns the file name without folders; rejects unsupported formats and empty or oversized files (US001)."""
        name = PurePath(filename.replace("\\", "/")).name[:255]
        extension = PurePath(name).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file format '{extension or name}'. Upload an Excel file ({', '.join(sorted(ALLOWED_EXTENSIONS))})"
            )
        if not content:
            raise ValueError("The file is empty")
        if len(content) > MAX_UPLOAD_BYTES:
            raise ValueError(f"The file exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit")
        return name

    def start_cleaning(self) -> None:
        self.upload_status = DatasetStatus.CLEANING
        self.error_message = None

    def await_confirmation(self) -> None:
        self.upload_status = DatasetStatus.AWAITING_CONFIRMATION

    def confirm_merge(self) -> None:
        if self.upload_status != DatasetStatus.AWAITING_CONFIRMATION:
            raise ValueError(f"The dataset is not waiting for confirmation (status: {self.upload_status.value})")
        self.upload_status = DatasetStatus.RAW

    def mark_ready(self, processed_path: str, row_count: int, processed_row_count: int) -> None:
        self.upload_status = DatasetStatus.READY
        self.processed_path = processed_path
        self.row_count = row_count
        self.processed_row_count = processed_row_count

    def mark_failed(self, message: str) -> None:
        self.upload_status = DatasetStatus.FAILED
        self.error_message = message
