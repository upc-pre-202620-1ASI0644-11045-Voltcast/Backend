from dataclasses import dataclass


@dataclass(frozen=True)
class GetUserByIdQuery:
    user_id: int


@dataclass(frozen=True)
class GetUserByUsernameQuery:
    username: str


@dataclass(frozen=True)
class GetUserByEmailQuery:
    email: str


@dataclass(frozen=True)
class GetAllUsersQuery:
    """Admin: list all users with optional filters"""
    role_name: str | None = None
    is_active: bool | None = None
    suspended_only: bool = False


@dataclass(frozen=True)
class GetSuspendedPastGraceQuery:
    """
    Admin: get users whose suspension has exceeded 30 days
    and are ready for permanent deletion.
    """
    pass
