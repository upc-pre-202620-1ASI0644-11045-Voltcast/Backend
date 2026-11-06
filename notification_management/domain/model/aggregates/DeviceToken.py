from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, TIMESTAMP, text
from sqlalchemy.orm import Mapped, mapped_column

from iam.domain.model.aggregates.User import User  # noqa: F401  the table the FK points to must be known
from shared.infrastructure.persistence.configuration.column_types import TinyInt
from shared.infrastructure.persistence.configuration.database_configuration import Base


class DeviceToken(Base):
    """
    Aggregate Root: a phone where a user is signed in, as FCM knows it. The push notifications go to these tokens.
    Not in ERD v1.0.4: the push needs to know which devices belong to which user.
    """
    __tablename__ = "device_token"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        TinyInt, ForeignKey("user.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, index=True
    )
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
