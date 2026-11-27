from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from cell_management.domain.model.aggregates.Cell import Cell
from notification_management.domain.model.aggregates.DeviceToken import DeviceToken
from notification_management.domain.model.aggregates.Notification import (
    Notification,
    NotificationChannel,
    NotificationStatus,
    NotificationType,
)
from notification_management.domain.repositories.NotificationRepository import NotificationRow
from voltage_forecasting.domain.model.aggregates.AlertRule import AlertRule
from voltage_forecasting.domain.model.aggregates.Prediction import Prediction


class NotificationRepositoryImpl:

    def __init__(self, session: AsyncSession):
        self._session = session

    async def find_type(self, code: str) -> NotificationType | None:
        """Find a notification type by its code."""
        result = await self._session.execute(select(NotificationType).where(NotificationType.type == code))
        return result.scalars().first()

    async def add_all(self, notifications: list[Notification]) -> None:
        """Persist several notifications in one commit."""
        self._session.add_all(notifications)
        await self._session.commit()

    async def save(self, notification: Notification) -> Notification:
        """Persist a notification and return it."""
        self._session.add(notification)
        await self._session.commit()
        return notification

    @staticmethod
    def _with_forecast():
        """Build the query that joins notifications with their prediction and cell."""
        return (
            select(Notification, Prediction, Cell)
            .outerjoin(Prediction, Prediction.id == Notification.prediction_id)
            .outerjoin(Cell, Cell.id == Prediction.cell_id)
        )

    async def find_pending(self, channel: NotificationChannel) -> list[NotificationRow]:
        """List the pending notifications of a channel, oldest first."""
        result = await self._session.execute(
            self._with_forecast()
            .where(Notification.status == NotificationStatus.PENDING, Notification.channel == channel)
            .order_by(Notification.id)
        )
        return [tuple(row) for row in result.unique().all()]

    async def find_general_limit(self) -> float | None:
        """The active maximum voltage that applies to every cell, for the text of the alerts."""
        result = await self._session.execute(
            select(AlertRule.max_voltage).where(AlertRule.is_active.is_(True), AlertRule.cell_id.is_(None)).limit(1)
        )
        return result.scalar_one_or_none()

    async def find_inbox(self, user_id: int, status: NotificationStatus | None, limit: int) -> list[NotificationRow]:
        """The push notifications of the user, the newest first: the inbox is where the push rows live."""
        stmt = self._with_forecast().where(Notification.user_id == user_id, Notification.channel == NotificationChannel.PUSH)
        if status is not None:
            stmt = stmt.where(Notification.status == status)
        result = await self._session.execute(stmt.order_by(Notification.id.desc()).limit(limit))
        return [tuple(row) for row in result.unique().all()]

    async def find_owned(self, user_id: int, notification_id: int) -> Notification | None:
        """Find a notification that belongs to the user."""
        result = await self._session.execute(
            select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id)
        )
        return result.unique().scalar_one_or_none()

    async def find_device_by_token(self, token: str) -> DeviceToken | None:
        """Find a registered device by its push token."""
        result = await self._session.execute(select(DeviceToken).where(DeviceToken.token == token))
        return result.scalar_one_or_none()

    async def find_device(self, user_id: int, device_id: int) -> DeviceToken | None:
        """Find a device that belongs to the user."""
        result = await self._session.execute(
            select(DeviceToken).where(DeviceToken.id == device_id, DeviceToken.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def save_device(self, device: DeviceToken) -> DeviceToken:
        """Persist a device token and return it refreshed."""
        self._session.add(device)
        await self._session.commit()
        await self._session.refresh(device)
        return device

    async def delete_device(self, device: DeviceToken) -> None:
        """Delete a registered device and commit."""
        await self._session.delete(device)
        await self._session.commit()

    async def find_tokens(self, user_id: int) -> list[str]:
        """List the push tokens of a user."""
        result = await self._session.execute(select(DeviceToken.token).where(DeviceToken.user_id == user_id))
        return list(result.scalars().all())

    async def delete_tokens(self, tokens: list[str]) -> None:
        """Delete the given push tokens, if any."""
        if tokens:
            await self._session.execute(delete(DeviceToken).where(DeviceToken.token.in_(tokens)))
            await self._session.commit()
