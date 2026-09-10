from iam.domain.model.aggregates.User import User
from iam.domain.model.queries.UserQueries import (
    GetUserByIdQuery,
    GetUserByUsernameQuery,
    GetUserByEmailQuery,
    GetAllUsersQuery,
)
from iam.domain.repositories.UserRepository import UserRepository


class QueryServiceImpl:
    """
    Query Service for IAM Context.
    Handles all read operations (CQRS).
    """

    def __init__(self, repository: UserRepository):
        self._repository = repository

    async def get_user_by_id(self, query: GetUserByIdQuery) -> User | None:
        return await self._repository.find_by_id(query.user_id)

    async def get_user_by_username(self, query: GetUserByUsernameQuery) -> User | None:
        return await self._repository.find_by_username(query.username)

    async def get_user_by_email(self, query: GetUserByEmailQuery) -> User | None:
        return await self._repository.find_by_email(query.email)

    async def get_all_users(self, query: GetAllUsersQuery) -> list[User]:
        return await self._repository.find_all(
            role_name=query.role_name,
            is_active=query.is_active,
            suspended_only=query.suspended_only,
        )

    async def get_suspended_past_grace(self) -> list[User]:
        """
        Returns users whose suspension has exceeded 30 days.
        Used by the admin panel to trigger permanent deletion.
        """
        all_suspended = await self._repository.find_all(suspended_only=True)
        return [u for u in all_suspended if u.is_past_grace_period()]