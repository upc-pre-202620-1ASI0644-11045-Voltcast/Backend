from datetime import datetime, timedelta, timezone

import bcrypt
from sqlalchemy import String, Integer, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from iam.domain.model.aggregates.Role import Role
from shared.domain.model.aggregates.base_entity import BaseEntity, utc_now


SUSPENSION_GRACE_DAYS = 30
PERMISSION_PROFILE_EDIT    = "profile_edit"
PERMISSION_PASSWORD_CHANGE = "password_change"


class UserPermission(BaseEntity):
    """
    Tabla normalizada de permisos por usuario
    PK compuesta (user_id, permission_type)
    """
    __tablename__ = "user_permissions"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "permission_type"),
    )

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_type: Mapped[str] = mapped_column(String(20), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(default=utc_now)


class User(BaseEntity):
    """
    Aggregate Root: Usuario del sistema IAM.
    Maneja autenticación, roles (FK a roles) y permisos de edición.
    """
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)

    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"), nullable=False)
    role: Mapped[Role] = relationship("Role", lazy="joined")

    permissions: Mapped[list[UserPermission]] = relationship(
        "UserPermission",
        cascade="all, delete-orphan",
        lazy="selectin",
        foreign_keys="UserPermission.user_id",
    )

    suspended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True, index=True)

    # =========================================================================
    # DOMAIN LOGIC — Password
    # =========================================================================

    @staticmethod
    def hash_password(plain_password: str) -> str:
        if not plain_password or len(plain_password) < 8:
            raise ValueError("Password must be at least 8 characters")
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(plain_password.encode('utf-8'), salt).decode('utf-8')

    def verify_password(self, plain_password: str) -> bool:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            self.hashed_password.encode('utf-8')
        )

    def change_password(self, old_password: str, new_password: str) -> None:
        """
        User changes their own password (requires prior admin permission).
        Permission is single-use — revoked automatically after the change.
        """
        if not self.can_change_password:
            raise ValueError("You do not have permission to change your password")
        if not self.verify_password(old_password):
            raise ValueError("Current password is incorrect")
        self.hashed_password = self.hash_password(new_password)
        self._revoke_permission(PERMISSION_PASSWORD_CHANGE)
        self.updated_at = utc_now()

    def force_change_password(self, new_password: str) -> None:
        """Admin resets a user's password directly (no old password needed)."""
        self.hashed_password = self.hash_password(new_password)
        self.updated_at = utc_now()

    # =========================================================================
    # DOMAIN LOGIC — Profile
    # =========================================================================

    def update_profile(self, full_name: str | None = None, email: str | None = None) -> None:
        """
        User updates their own profile (requires prior admin permission).
        Permission is single-use — revoked automatically after the change.
        """
        if not self.can_edit_profile:
            raise ValueError("You do not have permission to edit your profile")
        self._apply_profile(full_name, email)
        self._revoke_permission(PERMISSION_PROFILE_EDIT)

    def admin_update_profile(self, full_name: str | None = None, email: str | None = None) -> None:
        """Admin updates any user's profile without permission check."""
        self._apply_profile(full_name, email)

    def _apply_profile(self, full_name: str | None, email: str | None) -> None:
        if full_name is not None:
            self.full_name = full_name
        if email is not None:
            if '@' not in email:
                raise ValueError("Invalid email format")
            self.email = email
        self.updated_at = utc_now()

    # =========================================================================
    # DOMAIN LOGIC — Permissions (granted by admin)
    # =========================================================================

    def grant_profile_edit(self) -> None:
        self._grant_permission(PERMISSION_PROFILE_EDIT)
        self.updated_at = utc_now()

    def revoke_profile_edit(self) -> None:
        self._revoke_permission(PERMISSION_PROFILE_EDIT)
        self.updated_at = utc_now()

    def grant_password_change(self) -> None:
        self._grant_permission(PERMISSION_PASSWORD_CHANGE)
        self.updated_at = utc_now()

    def revoke_password_change(self) -> None:
        self._revoke_permission(PERMISSION_PASSWORD_CHANGE)
        self.updated_at = utc_now()

    # ── Permission helpers ────────────────────────────────────────────────────

    @property
    def can_edit_profile(self) -> bool:
        return any(p.permission_type == PERMISSION_PROFILE_EDIT for p in self.permissions)

    @property
    def can_change_password(self) -> bool:
        return any(p.permission_type == PERMISSION_PASSWORD_CHANGE for p in self.permissions)

    def _grant_permission(self, permission_type: str) -> None:
        if not any(p.permission_type == permission_type for p in self.permissions):
            self.permissions.append(UserPermission(user_id=self.id, permission_type=permission_type))

    def _revoke_permission(self, permission_type: str) -> None:
        self.permissions = [p for p in self.permissions if p.permission_type != permission_type]

    # =========================================================================
    # DOMAIN LOGIC — Account lifecycle
    # =========================================================================

    def suspend(self) -> None:
        if not self.is_active:
            raise ValueError("Account is already deactivated")
        if self.is_admin():
            raise ValueError("Admin account cannot be suspended through the application")
        now = utc_now()
        self.is_active = False
        self.suspended_at = now
        self.expires_at = now + timedelta(days=SUSPENSION_GRACE_DAYS)
        self.updated_at = now

    def reactivate(self) -> None:
        if self.is_active:
            raise ValueError("Account is already active")
        if self.is_past_grace_period():
            raise ValueError("Grace period expired — account must be permanently deleted")
        self.is_active = True
        self.suspended_at = None
        self.expires_at = None
        self.updated_at = utc_now()

    def deactivate(self) -> None:
        """Legacy deactivate (self-initiated). Kept for backwards compatibility."""
        if not self.is_active:
            raise ValueError("User account is already deactivated")
        self.is_active = False
        self.updated_at = utc_now()

    def activate(self) -> None:
        """Legacy activate. Kept for backwards compatibility."""
        if self.is_active:
            raise ValueError("User account is already active")
        self.is_active = True
        self.updated_at = utc_now()

    # =========================================================================
    # BUSINESS RULES
    # =========================================================================

    def can_authenticate(self) -> bool:
        return self.is_active

    def is_admin(self) -> bool:
        return self.role is not None and self.role.name == "ADMIN"

    def is_past_grace_period(self) -> bool:
        if not self.expires_at:
            return False
        expires = self.expires_at.replace(tzinfo=timezone.utc) if self.expires_at.tzinfo is None else self.expires_at
        return utc_now() >= expires

    def days_until_deletion(self) -> int | None:
        if not self.expires_at:
            return None
        expires = self.expires_at.replace(tzinfo=timezone.utc) if self.expires_at.tzinfo is None else self.expires_at
        remaining = (expires - utc_now()).days
        return max(remaining, 0)

    # =========================================================================
    # SERIALIZATION
    # =========================================================================

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "is_active": self.is_active,
            "role": self.role.name if self.role else None,
            "can_edit_profile": self.can_edit_profile,
            "can_change_password": self.can_change_password,
            "suspended_at": self.suspended_at.isoformat() if self.suspended_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "days_until_deletion": self.days_until_deletion(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
