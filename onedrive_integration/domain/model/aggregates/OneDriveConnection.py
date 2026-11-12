from datetime import date, datetime

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text, TIMESTAMP, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from dataset_management.domain.model.aggregates.UploadedDataset import UploadedDataset  # noqa: F401  the table the FK points to must be known
from iam.domain.model.aggregates.User import User  # noqa: F401  the table the FK points to must be known
from shared.infrastructure.persistence.configuration.column_types import SmallInt, TinyInt
from shared.infrastructure.persistence.configuration.database_configuration import Base

ERROR_INVALID_GRANT = "invalid_grant"
ERROR_SYNC_FAILED = "sync_failed"

FILE_PENDING = "pending"    # valid and continuous: waits until there are enough new days to retrain
FILE_HELD = "held"          # valid but there is a gap before it: waits for the days in between
FILE_CONSUMED = "consumed"  # part of a dataset
FILE_REJECTED = "rejected"  # not an Excel with voltages, or it adds no new days; `reason` says why


class OneDriveConnection(Base):
    """The company's OneDrive account. There is only one (id 1): connecting again replaces it. The token is encrypted."""
    __tablename__ = "onedrive_connection"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    account: Mapped[str] = mapped_column(String(255), nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[str | None] = mapped_column(String(30), nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)
    connected_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class OneDriveOAuthState(Base):
    """The `state` of one authorization request: random, single use, short lived and tied to the supervisor who asked. Only its hash is kept."""
    __tablename__ = "onedrive_oauth_state"

    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(TinyInt, ForeignKey("user.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("0"))


class OneDriveFile(Base):
    """A file of the OneDrive folder the sync has seen, by id and version (eTag), so each version is looked at once."""
    __tablename__ = "onedrive_file"
    __table_args__ = (UniqueConstraint("item_id", "etag"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    etag: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    date_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(255), nullable=True)  # a copy, so the dataset does not depend on OneDrive later
    dataset_id: Mapped[int | None] = mapped_column(SmallInt, ForeignKey("uploaded_dataset.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
