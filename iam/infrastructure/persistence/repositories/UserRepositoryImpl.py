from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from iam.domain.model.aggregates.Role import Role
from iam.domain.model.aggregates.User import User, UserStatus


class UserRepositoryImpl:

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, user: User) -> User:
        self._session.add(user)
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def find_by_id(self, user_id: int) -> User | None:
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def find_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def find_all(self, status: UserStatus | None = None) -> list[User]:
        stmt = select(User)
        if status is not None:
            stmt = stmt.where(User.status == status)
        result = await self._session.execute(stmt.order_by(User.id.desc()))
        return list(result.scalars().all())

    async def exists_by_email(self, email: str) -> bool:
        result = await self._session.execute(select(User.id).where(User.email == email))
        return result.scalar_one_or_none() is not None

    async def find_role_by_name(self, name: str) -> Role | None:
        result = await self._session.execute(select(Role).where(Role.name == name.upper()))
        return result.scalars().first()
