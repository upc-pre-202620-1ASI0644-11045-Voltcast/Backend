from dataclasses import dataclass

from iam.domain.model.aggregates.User import UserStatus


@dataclass(frozen=True)
class GetUserByIdQuery:
    user_id: int


@dataclass(frozen=True)
class GetAllUsersQuery:
    """Supervisor: list users, optionally filtered by status"""
    status: UserStatus | None = None
