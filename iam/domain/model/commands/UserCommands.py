from dataclasses import dataclass


@dataclass(frozen=True)
class SignInCommand:
    """Command: authenticate a user with email and password"""
    email: str
    password: str


@dataclass(frozen=True)
class RegisterUserCommand:
    """Command: an engineer requests the creation of an account"""
    full_name: str
    email: str
    password: str


@dataclass(frozen=True)
class ReviewRegistrationCommand:
    """Command: a supervisor approves (assigning a role) or rejects a pending request"""
    user_id: int
    approve: bool
    role_name: str | None = None


@dataclass(frozen=True)
class UpdateUserCommand:
    """Command: a supervisor edits the data of a registered account"""
    user_id: int
    full_name: str | None = None
    email: str | None = None


@dataclass(frozen=True)
class ChangeUserStatusCommand:
    """Command: a supervisor disables or re-enables an account"""
    user_id: int
    enable: bool
