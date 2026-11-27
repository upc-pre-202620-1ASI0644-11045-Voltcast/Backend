from typing import Protocol
from iam.domain.model.aggregates.Role import Role
from iam.domain.model.aggregates.User import User, UserStatus


class UserRepository(Protocol):

    async def save(self, user: User) -> User:
        """Persist a user and return it."""
        ...
    async def find_by_id(self, user_id: int) -> User | None:
        """Find a user by id."""
        ...
    async def find_by_email(self, email: str) -> User | None:
        """Find a user by email."""
        ...
    async def find_all(self, status: UserStatus | None = None) -> list[User]:
        """List users, optionally filtered by status."""
        ...
    async def exists_by_email(self, email: str) -> bool:
        """Tell whether a user with this email exists."""
        ...
    async def find_role_by_name(self, name: str) -> Role | None:
        """Find a role by its name."""
        ...
