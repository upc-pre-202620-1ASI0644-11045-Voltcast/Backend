from datetime import datetime
from enum import Enum

from sqlalchemy import Enum as SAEnum, ForeignKey, Index, Integer, String, TIMESTAMP, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from iam.domain.model.aggregates.User import User  # noqa: F401  the tables the FKs point to must be known
from shared.infrastructure.persistence.configuration.column_types import TinyInt
from shared.infrastructure.persistence.configuration.database_configuration import Base
from voltage_forecasting.domain.model.aggregates.Prediction import Prediction  # noqa: F401

PASSWORD_CHANGED = "P"    # US024
ACCESS_REQUESTED = "R"    # US025
ACCOUNT_ACCEPTED = "A"    # US029
ACCOUNT_REJECTED = "X"    # US030
VOLTAGE_EXCEEDED = "V"    # US026
DATE_NEAR = "D"           # US028

# Seeded at startup. The message (max 60 chars) is the subject / title of the notification.
NOTIFICATION_TYPES = {
    PASSWORD_CHANGED: "Contraseña cambiada",
    ACCESS_REQUESTED: "Nueva solicitud de registro",
    ACCOUNT_ACCEPTED: "Tu cuenta fue aceptada",
    ACCOUNT_REJECTED: "Tu cuenta fue rechazada",
    VOLTAGE_EXCEEDED: "Voltaje excesivo pronosticado",
    DATE_NEAR: "Revisa la celda: voltaje excesivo próximo",
}


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    READ = "read"


class NotificationChannel(str, Enum):
    PUSH = "push"
    EMAIL = "email"


def _values(enum) -> list[str]:
    return [member.value for member in enum]


# Channels of the account events; the voltage alerts (V, D) are queued as push rows by the Job that creates them.
CHANNELS = {
    PASSWORD_CHANGED: [NotificationChannel.EMAIL],
    ACCESS_REQUESTED: [NotificationChannel.EMAIL, NotificationChannel.PUSH],
    ACCOUNT_ACCEPTED: [NotificationChannel.EMAIL, NotificationChannel.PUSH],
    ACCOUNT_REJECTED: [NotificationChannel.EMAIL, NotificationChannel.PUSH],
}

_BODIES = {
    PASSWORD_CHANGED: "Tu contraseña fue cambiada",
    ACCESS_REQUESTED: "Hay una nueva solicitud de acceso pendiente de revisión",
    ACCOUNT_ACCEPTED: "Ya puedes iniciar sesión en VoltCast",
    ACCOUNT_REJECTED: "Tu solicitud de acceso fue rechazada",
}


def describe(type_code: str, cell_name: str | None, prediction_date: datetime | None, voltage: float | None) -> str:
    """Text of a notification, for the push and for the inbox (the title is the message of its type)."""
    if type_code in (VOLTAGE_EXCEEDED, DATE_NEAR) and cell_name and prediction_date is not None and voltage is not None:
        return f"{cell_name}: {voltage:.3f} V pronosticados para el {prediction_date:%d/%m/%Y}"
    return _BODIES.get(type_code, "")


class NotificationType(Base):
    """Catálogo de tipos de notificación (ver NOTIFICATION_TYPES)."""
    __tablename__ = "notification_type"

    id: Mapped[int] = mapped_column(TinyInt, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(1), nullable=False)
    message: Mapped[str] = mapped_column(String(60), nullable=False)


class Notification(Base):
    """
    Aggregate Root: un aviso para un usuario por un canal. Nace `pending` y pasa a `sent` cuando el canal lo entrega;
    si la entrega falla sigue `pending` y se reintenta. Hay una fila por canal.
    shortcut: the ERD column `channel` is a SET; every row has exactly one channel, so it is an enum here.
    """
    __tablename__ = "notification"
    __table_args__ = (
        Index("idx_notif_user_status", "user_id", "status"),
        # A forecast is announced once per user and channel (rows without forecast are never equal: NULLs differ).
        UniqueConstraint("user_id", "prediction_id", "notification_type_id", "channel", name="uq_notif_event"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        TinyInt, ForeignKey("user.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    prediction_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("prediction.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        SAEnum(NotificationChannel, values_callable=_values),
        nullable=False,
        default=NotificationChannel.PUSH,
        server_default=NotificationChannel.PUSH.value,
    )
    status: Mapped[NotificationStatus] = mapped_column(
        SAEnum(NotificationStatus, values_callable=_values),
        nullable=False,
        default=NotificationStatus.PENDING,
        server_default=NotificationStatus.PENDING.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    notification_type_id: Mapped[int] = mapped_column(
        TinyInt, ForeignKey("notification_type.id"), nullable=False
    )
    notification_type: Mapped[NotificationType] = relationship("NotificationType", lazy="joined")
