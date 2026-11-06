from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from notification_management.domain.model.aggregates.Notification import (
    Notification,
    NotificationChannel,
    NotificationStatus,
    NotificationType,
)


class NotificationRepositoryImpl:

    def __init__(self, session: AsyncSession):
        self._session = session

    async def find_type(self, code: str) -> NotificationType | None:
        result = await self._session.execute(select(NotificationType).where(NotificationType.type == code))
        return result.scalars().first()

    async def add_all(self, notifications: list[Notification]) -> None:
        self._session.add_all(notifications)
        await self._session.commit()

    async def save(self, notification: Notification) -> Notification:
        self._session.add(notification)
        await self._session.commit()
        return notification

    async def find_pending(self, channel: NotificationChannel) -> list[Notification]:
        result = await self._session.execute(
            select(Notification)
            .where(Notification.status == NotificationStatus.PENDING, Notification.channel == channel)
            .order_by(Notification.id)
        )
        return list(result.scalars().unique().all())
