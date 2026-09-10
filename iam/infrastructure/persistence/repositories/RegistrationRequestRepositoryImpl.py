from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from iam.domain.model.aggregates.RegistrationRequest import RegistrationRequest, RegistrationStatus
from iam.domain.repositories.RegistrationRequestRepository import RegistrationRequestRepository


class RegistrationRequestRepositoryImpl:

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, request: RegistrationRequest) -> RegistrationRequest:
        self._session.add(request)
        await self._session.flush()
        return request

    async def find_by_id(self, request_id: int) -> RegistrationRequest | None:
        result = await self._session.execute(
            select(RegistrationRequest).where(RegistrationRequest.id == request_id)
        )
        return result.scalar_one_or_none()

    async def find_by_email(self, email: str) -> RegistrationRequest | None:
        result = await self._session.execute(
            select(RegistrationRequest).where(RegistrationRequest.email == email.lower().strip())
        )
        return result.scalar_one_or_none()

    async def list_by_status(self, status: RegistrationStatus, offset: int, limit: int) -> list[RegistrationRequest]:
        result = await self._session.execute(
            select(RegistrationRequest)
            .where(RegistrationRequest.status == status)
            .order_by(RegistrationRequest.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_by_status(self, status: RegistrationStatus) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(RegistrationRequest).where(RegistrationRequest.status == status)
        )
        return result.scalar_one()

    async def save(self, request: RegistrationRequest) -> RegistrationRequest:
        await self._session.flush()
        return request
