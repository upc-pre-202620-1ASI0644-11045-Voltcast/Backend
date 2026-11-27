from typing import Protocol

from cell_management.domain.model.aggregates.Cell import Cell
from notification_management.domain.model.aggregates.DeviceToken import DeviceToken
from notification_management.domain.model.aggregates.Notification import (
    Notification,
    NotificationChannel,
    NotificationStatus,
    NotificationType,
)
from voltage_forecasting.domain.model.aggregates.Prediction import Prediction

# A notification with the forecast and the cell it is about, when it is about one.
NotificationRow = tuple[Notification, Prediction | None, Cell | None]


class NotificationRepository(Protocol):

    async def find_type(self, code: str) -> NotificationType | None:
        """Find a notification type by its code."""
        ...
    async def add_all(self, notifications: list[Notification]) -> None:
        """Persist several notifications."""
        ...
    async def save(self, notification: Notification) -> Notification:
        """Persist a notification and return it."""
        ...
    async def find_pending(self, channel: NotificationChannel) -> list[NotificationRow]:
        """List the pending notifications of a channel with their forecast data."""
        ...
    async def find_general_limit(self) -> float | None:
        """Return the general voltage limit, if one is set."""
        ...
    async def find_inbox(self, user_id: int, status: NotificationStatus | None, limit: int) -> list[NotificationRow]:
        """List the notifications of a user with their forecast data."""
        ...
    async def find_owned(self, user_id: int, notification_id: int) -> Notification | None:
        """Find a notification that belongs to the user."""
        ...

    async def find_device_by_token(self, token: str) -> DeviceToken | None:
        """Find a registered device by its push token."""
        ...
    async def find_device(self, user_id: int, device_id: int) -> DeviceToken | None:
        """Find a device that belongs to the user."""
        ...
    async def save_device(self, device: DeviceToken) -> DeviceToken:
        """Persist a device token and return it."""
        ...
    async def delete_device(self, device: DeviceToken) -> None:
        """Delete a registered device."""
        ...
    async def find_tokens(self, user_id: int) -> list[str]:
        """List the push tokens of a user."""
        ...
    async def delete_tokens(self, tokens: list[str]) -> None:
        """Delete the given push tokens."""
        ...
