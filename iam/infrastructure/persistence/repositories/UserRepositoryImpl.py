from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from iam.domain.model.aggregates.User import User
from iam.domain.model.aggregates.Role import Role


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

    async def find_by_username(self, username: str) -> User | None:
        result = await self._session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def find_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def find_by_username_or_email(self, username_or_email: str) -> User | None:
        result = await self._session.execute(
            select(User).where(
                or_(User.username == username_or_email, User.email == username_or_email)
            )
        )
        return result.scalar_one_or_none()

    async def find_all(
        self,
        role_name: str | None = None,
        is_active: bool | None = None,
        suspended_only: bool = False,
    ) -> list[User]:
        stmt = select(User).join(Role)
        filters = []

        if role_name is not None:
            filters.append(Role.name == role_name.upper())
        if is_active is not None:
            filters.append(User.is_active == is_active)
        if suspended_only:
            filters.append(User.suspended_at.isnot(None))

        if filters:
            stmt = stmt.where(and_(*filters))

        stmt = stmt.order_by(User.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, user: User) -> None:
        await self._session.delete(user)
        await self._session.commit()

    async def exists_by_username(self, username: str) -> bool:
        result = await self._session.execute(select(User.id).where(User.username == username))
        return result.scalar_one_or_none() is not None

    async def exists_by_email(self, email: str) -> bool:
        result = await self._session.execute(select(User.id).where(User.email == email))
        return result.scalar_one_or_none() is not None

    async def find_role_by_name(self, name: str) -> Role | None:
        result = await self._session.execute(
            select(Role).where(Role.name == name.upper())
        )
        return result.scalar_one_or_none()
