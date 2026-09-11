from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from iam.domain.model.aggregates.PasswordReset import PasswordReset


class PasswordResetRepositoryImpl:

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, entry: PasswordReset) -> PasswordReset:
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def find_latest_active(self, user_id: int) -> PasswordReset | None:
        result = await self._session.execute(
            select(PasswordReset)
            .where(PasswordReset.user_id == user_id, PasswordReset.used == False)
            .order_by(PasswordReset.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def invalidate_all_for_user(self, user_id: int) -> None:
        await self._session.execute(
            update(PasswordReset)
            .where(PasswordReset.user_id == user_id, PasswordReset.used == False)
            .values(used=True)
        )
