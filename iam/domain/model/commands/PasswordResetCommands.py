from dataclasses import dataclass


@dataclass(frozen=True)
class RequestPasswordResetCommand:
    """User requests a password reset code via email"""
    email: str


@dataclass(frozen=True)
class ConfirmPasswordResetCommand:
    """User confirms password reset with the code received"""
    email: str
    code: str
    new_password: str
