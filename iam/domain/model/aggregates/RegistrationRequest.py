from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import String, Enum as SAEnum, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.persistence.configuration.database_configuration import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RegistrationStatus(str, Enum):
    PENDING  = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RegistrationRequest(Base):
    """
    Solicitud de registro creada por un ingeniero de planta.
    Se mantiene hasta que el supervisor la revise (approve/reject).
    """
    __tablename__ = "registration_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    status: Mapped[RegistrationStatus] = mapped_column(
        SAEnum(RegistrationStatus), nullable=False, default=RegistrationStatus.PENDING
    )

    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def approve(self) -> None:
        self.status = RegistrationStatus.APPROVED
        self.reviewed_at = utc_now()

    def reject(self) -> None:
        self.status = RegistrationStatus.REJECTED
        self.reviewed_at = utc_now()
