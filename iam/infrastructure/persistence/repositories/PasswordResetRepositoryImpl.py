from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from iam.domain.model.aggregates.PasswordReset import PasswordReset


class PasswordResetRepositoryImpl:

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, entry: PasswordReset) -> PasswordReset:
        self._session.add(entry)
        await self._session.commit()
        await self._session.refresh(entry)
        return entry

    async def find_by_user(self, user_id: int) -> PasswordReset | None:
        result = await self._session.execute(
            select(PasswordReset)
            .where(PasswordReset.user_id == user_id)
            .order_by(PasswordReset.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
