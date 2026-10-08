import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import String, Boolean, ForeignKey, TIMESTAMP, text

from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.persistence.configuration.column_types import TinyInt
from shared.infrastructure.persistence.configuration.database_configuration import Base

RESET_CODE_EXPIRY_MINUTES = 15


def utc_now_naive() -> datetime:
    """UTC datetime without tzinfo, as stored in TIMESTAMP columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PasswordReset(Base):
    """Código de verificación temporal para la recuperación de contraseña."""
    __tablename__ = "password_reset"

    id: Mapped[int] = mapped_column(TinyInt, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(TinyInt, ForeignKey("user.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)

    @classmethod
    def issue_for(cls, user_id: int) -> "PasswordReset":
        entry = cls(user_id=user_id)
        entry.renew()
        return entry

    def renew(self) -> None:
        """Replaces the code: the previous one stops being valid even if it had not expired yet."""
        self.code = f"{secrets.randbelow(1_000_000):06d}"
        self.used = False
        self.expires_at = utc_now_naive() + timedelta(minutes=RESET_CODE_EXPIRY_MINUTES)

    def mark_used(self) -> None:
        self.used = True

    def is_expired(self) -> bool:
        return utc_now_naive() > self.expires_at

    def is_valid(self, code: str) -> bool:
        return not self.used and not self.is_expired() and secrets.compare_digest(self.code, code)
