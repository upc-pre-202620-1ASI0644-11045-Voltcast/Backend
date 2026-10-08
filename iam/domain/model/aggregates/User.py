import re
from enum import Enum

import bcrypt
from sqlalchemy import String, ForeignKey, TIMESTAMP, text
from sqlalchemy import Enum as SAEnum

from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from iam.domain.model.aggregates.Role import Role, ROLE_ADMIN, ROLE_USER
from shared.infrastructure.persistence.configuration.column_types import TinyInt
from shared.infrastructure.persistence.configuration.database_configuration import Base


class UserStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    REJECTED = "rejected"
    DISABLED = "disabled"


class User(Base):
    """
    Aggregate Root: Usuario del sistema IAM.
    Flujo de estado: pending -> active | rejected, active <-> disabled.
    El rol se asigna al aprobar la solicitud.
    """
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(TinyInt, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role_id: Mapped[int | None] = mapped_column(
        TinyInt, ForeignKey("role.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=True
    )
    role: Mapped[Role | None] = relationship("Role", lazy="joined")
    status: Mapped[UserStatus] = mapped_column(
        SAEnum(UserStatus, values_callable=lambda enum: [member.value for member in enum]),
        nullable=False,
        default=UserStatus.PENDING,
        server_default=UserStatus.PENDING.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    # =========================================================================
    # DOMAIN LOGIC — Password (RNF-02, RNF-03)
    # =========================================================================

    @staticmethod
    def validate_password_policy(plain_password: str) -> None:
        errors = []
        if len(plain_password) < 8:
            errors.append("at least 8 characters")
        if not re.search(r"[A-Z]", plain_password):
            errors.append("an uppercase letter")
        if not re.search(r"[a-z]", plain_password):
            errors.append("a lowercase letter")
        if not re.search(r"\d", plain_password):
            errors.append("a number")
        if not re.search(r"[^A-Za-z0-9]", plain_password):
            errors.append("a special character")
        if errors:
            raise ValueError("Password must contain " + ", ".join(errors))

    @staticmethod
    def hash_password(plain_password: str) -> str:
        User.validate_password_policy(plain_password)
        return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def verify_password(self, plain_password: str) -> bool:
        return bcrypt.checkpw(plain_password.encode("utf-8"), self.hashed_password.encode("utf-8"))

    def reset_password(self, new_password: str) -> None:
        self.hashed_password = self.hash_password(new_password)

    # =========================================================================
    # DOMAIN LOGIC — Registration review and account lifecycle
    # =========================================================================

    def approve(self, role: Role) -> None:
        if self.status != UserStatus.PENDING:
            raise ValueError("Only pending requests can be approved")
        self.role = role
        self.status = UserStatus.ACTIVE

    def reject(self) -> None:
        if self.status != UserStatus.PENDING:
            raise ValueError("Only pending requests can be rejected")
        self.status = UserStatus.REJECTED

    def resubmit(self, full_name: str, hashed_password: str) -> None:
        """A rejected applicant asks again: the same row goes back to pending (ids are never reused)."""
        if self.status != UserStatus.REJECTED:
            raise ValueError("Only rejected requests can be submitted again")
        self.full_name = full_name
        self.hashed_password = hashed_password
        self.status = UserStatus.PENDING

    def disable(self) -> None:
        if self.status != UserStatus.ACTIVE:
            raise ValueError("Only active accounts can be disabled")
        self.status = UserStatus.DISABLED

    def enable(self) -> None:
        if self.status != UserStatus.DISABLED:
            raise ValueError("Only disabled accounts can be enabled")
        self.status = UserStatus.ACTIVE

    def update_profile(self, full_name: str | None = None, email: str | None = None) -> None:
        if full_name is not None:
            self.full_name = full_name
        if email is not None:
            self.email = email

    # =========================================================================
    # BUSINESS RULES
    # =========================================================================

    def can_authenticate(self) -> bool:
        return self.status == UserStatus.ACTIVE

    def is_admin(self) -> bool:
        return self.role is not None and self.role.name == ROLE_ADMIN

    def is_engineer(self) -> bool:
        return self.role is not None and self.role.name == ROLE_USER
