from dataclasses import dataclass


@dataclass(frozen=True)
class CreateSignUpRequestCommand:
    """Public user submits a registration request"""
    full_name: str
    email: str
    password: str


@dataclass(frozen=True)
class ApproveSignUpRequestCommand:
    """Supervisor approves a pending registration request"""
    request_id: int


@dataclass(frozen=True)
class RejectSignUpRequestCommand:
    """Supervisor rejects a pending registration request"""
    request_id: int
