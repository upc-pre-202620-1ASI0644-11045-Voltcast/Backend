from datetime import datetime, timezone
from sqlalchemy import DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column, declared_attr
from shared.infrastructure.persistence.configuration.database_configuration import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BaseEntity(Base):
    """
    Abstract base class for all domain entities.
    Provides common fields: id, created_at, updated_at.
    """
    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False
    )

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower()
