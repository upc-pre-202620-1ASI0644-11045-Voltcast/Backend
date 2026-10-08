from iam.domain.model.aggregates.User import User
from iam.domain.model.queries.UserQueries import GetUserByIdQuery, GetAllUsersQuery
from iam.domain.repositories.UserRepository import UserRepository


class QueryServiceImpl:
    """Query Service for the IAM context."""

    def __init__(self, repository: UserRepository):
        self._repository = repository

    async def get_user_by_id(self, query: GetUserByIdQuery) -> User | None:
        return await self._repository.find_by_id(query.user_id)

    async def get_all_users(self, query: GetAllUsersQuery) -> list[User]:
        return await self._repository.find_all(status=query.status)
