import logging

from iam.domain.model.aggregates.Role import ROLE_ADMIN
from iam.domain.model.aggregates.User import User, UserStatus
from iam.domain.repositories.UserRepository import UserRepository
from notification_management.domain.model.aggregates.Notification import (
    ACCESS_REQUESTED,
    ACCOUNT_ACCEPTED,
    ACCOUNT_REJECTED,
    PASSWORD_CHANGED,
    Notification,
    NotificationChannel,
    NotificationStatus,
)
from notification_management.domain.repositories.NotificationRepository import NotificationRepository
from shared.infrastructure.email.email_client import (
    send_account_accepted_notification,
    send_account_rejected_notification,
    send_new_registration_request_notification,
    send_password_changed_notification,
)

logger = logging.getLogger(__name__)


class NotificationServiceImpl:
    """
    Outbox of the notifications: every event stores a `pending` row per user and the email is sent right after.
    A send that fails (no SMTP, no connection) leaves the row `pending`; the next dispatch sends it (US029/US030 E02).
    """

    def __init__(self, repository: NotificationRepository, user_repository: UserRepository):
        self._repository = repository
        self._users = user_repository

    async def notify(self, type_code: str, users: list[User]) -> None:
        notification_type = await self._repository.find_type(type_code)
        if notification_type is None:
            raise ValueError(f"Unknown notification type: {type_code}")
        await self._repository.add_all([
            Notification(user_id=user.id, notification_type_id=notification_type.id, channel=NotificationChannel.EMAIL)
            for user in users
        ])
        await self.dispatch_pending()

    async def notify_supervisors(self, type_code: str) -> None:
        supervisors = [
            user for user in await self._users.find_all(UserStatus.ACTIVE) if user.role and user.role.name == ROLE_ADMIN
        ]
        await self.notify(type_code, supervisors)

    async def dispatch_pending(self) -> None:
        """
        Sends every pending email, the oldest first. One failure does not stop the rest.
        shortcut: no row lock, two dispatches at the same time can send the same email twice; lock the rows if it matters.
        """
        for notification in await self._repository.find_pending(NotificationChannel.EMAIL):
            try:
                user = await self._users.find_by_id(notification.user_id)
                await self._send(notification.notification_type.type, user)
                notification.status = NotificationStatus.SENT
                await self._repository.save(notification)
            except Exception:
                logger.exception("Notification %s could not be sent; it stays pending", notification.id)

    async def _send(self, type_code: str, user: User) -> None:
        if type_code == PASSWORD_CHANGED:
            await send_password_changed_notification(user.email, user.full_name)
        elif type_code == ACCOUNT_ACCEPTED:
            await send_account_accepted_notification(user.email, user.full_name)
        elif type_code == ACCOUNT_REJECTED:
            await send_account_rejected_notification(user.email, user.full_name)
        elif type_code == ACCESS_REQUESTED:
            # The requester is not stored in the notification: the email lists the requests still pending now.
            pending = await self._users.find_all(UserStatus.PENDING)
            if pending:
                await send_new_registration_request_notification(user.email, [(p.full_name, p.email) for p in pending])
        else:
            raise ValueError(f"No email for notification type {type_code}")
