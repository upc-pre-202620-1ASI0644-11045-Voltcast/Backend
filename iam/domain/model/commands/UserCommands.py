from dataclasses import dataclass


@dataclass(frozen=True)
class SignInCommand:
    """Command: Authenticate user"""
    username_or_email: str
    password: str


@dataclass(frozen=True)
class ChangePasswordCommand:
    """Command: User changes their own password (requires admin permission)"""
    user_id: int
    old_password: str
    new_password: str


@dataclass(frozen=True)
class UpdateProfileCommand:
    """Command: User updates their own profile (requires admin permission)"""
    user_id: int
    full_name: str | None = None
    email: str | None = None


@dataclass(frozen=True)
class DeactivateUserCommand:
    """Command: User deactivates their own account (legacy)"""
    user_id: int


# ── Admin commands ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AdminCreateUserCommand:
    """Command: Admin creates a new user with an assigned role"""
    username: str
    email: str
    password: str
    role_name: str
    requested_by_id: int
    full_name: str | None = None


@dataclass(frozen=True)
class AdminChangeRoleCommand:
    """Command: Admin changes a user's role"""
    target_user_id: int
    new_role_name: str
    requested_by_id: int


@dataclass(frozen=True)
class AdminGrantProfileEditCommand:
    """Command: Admin grants permission to edit profile"""
    target_user_id: int
    requested_by_id: int


@dataclass(frozen=True)
class AdminRevokeProfileEditCommand:
    """Command: Admin revokes permission to edit profile"""
    target_user_id: int
    requested_by_id: int


@dataclass(frozen=True)
class AdminGrantPasswordChangeCommand:
    """Command: Admin grants permission to change password"""
    target_user_id: int
    requested_by_id: int


@dataclass(frozen=True)
class AdminRevokePasswordChangeCommand:
    """Command: Admin revokes permission to change password"""
    target_user_id: int
    requested_by_id: int


@dataclass(frozen=True)
class AdminSuspendUserCommand:
    """Command: Admin suspends a user — starts 30-day grace period"""
    target_user_id: int
    requested_by_id: int


@dataclass(frozen=True)
class AdminReactivateUserCommand:
    """Command: Admin cancels suspension within the 30-day grace window"""
    target_user_id: int
    requested_by_id: int


@dataclass(frozen=True)
class AdminForcePasswordResetCommand:
    """Command: Admin sets a new password for a user directly"""
    target_user_id: int
    new_password: str
    requested_by_id: int


@dataclass(frozen=True)
class AdminUpdateProfileCommand:
    """Command: Admin updates any user's profile directly"""
    target_user_id: int
    requested_by_id: int
    full_name: str | None = None
    email: str | None = None
