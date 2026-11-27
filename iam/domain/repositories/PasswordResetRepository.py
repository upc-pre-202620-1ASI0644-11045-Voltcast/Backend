from typing import Protocol

from iam.domain.model.aggregates.PasswordReset import PasswordReset


class PasswordResetRepository(Protocol):
    async def save(self, entry: PasswordReset) -> PasswordReset:
        """Persist a password reset entry and return it."""
        ...
    async def find_by_user(self, user_id: int) -> PasswordReset | None:
        """Find the password reset entry of a user."""
        ...
