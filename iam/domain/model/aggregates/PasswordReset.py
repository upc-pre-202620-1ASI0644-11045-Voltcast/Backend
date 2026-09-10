import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.persistence.configuration.database_configuration import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


RESET_CODE_EXPIRY_MINUTES = 15


class PasswordReset(Base):
    """Codigo de verificacion para recuperacion de contrasena."""
    __tablename__ = "password_resets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(6), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    def is_expired(self) -> bool:
        expires_at = self.created_at + timedelta(minutes=RESET_CODE_EXPIRY_MINUTES)
        return utc_now() > expires_at

    def is_valid(self, code: str) -> bool:
        return not self.used and not self.is_expired() and secrets.compare_digest(self.code, code)

    @staticmethod
    def generate_code() -> str:
        return f"{secrets.randbelow(1_000_000):06d}"
