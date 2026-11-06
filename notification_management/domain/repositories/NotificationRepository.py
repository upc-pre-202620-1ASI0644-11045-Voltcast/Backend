from typing import Protocol

from notification_management.domain.model.aggregates.Notification import (
    Notification,
    NotificationChannel,
    NotificationType,
)


class NotificationRepository(Protocol):

    async def find_type(self, code: str) -> NotificationType | None: ...
    async def add_all(self, notifications: list[Notification]) -> None: ...
    async def save(self, notification: Notification) -> Notification: ...
    async def find_pending(self, channel: NotificationChannel) -> list[Notification]: ...
