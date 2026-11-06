import logging

from cell_management.domain.model.aggregates.Cell import Cell
from iam.domain.model.aggregates.Role import ROLE_ADMIN
from iam.domain.model.aggregates.User import User, UserStatus
from iam.domain.repositories.UserRepository import UserRepository
from notification_management.domain.model.aggregates.DeviceToken import DeviceToken
from notification_management.domain.model.aggregates.Notification import (
    ACCESS_REQUESTED,
    ACCOUNT_ACCEPTED,
    ACCOUNT_REJECTED,
    CHANNELS,
    PASSWORD_CHANGED,
    Notification,
    NotificationChannel,
    NotificationStatus,
    describe,
)
from notification_management.domain.repositories.NotificationRepository import NotificationRepository
from shared.domain.exceptions.domain_exceptions import EntityNotFoundException
from shared.infrastructure.email.email_client import (
    send_account_accepted_notification,
    send_account_rejected_notification,
    send_new_registration_request_notification,
    send_password_changed_notification,
)
from shared.infrastructure.push.fcm_client import send_push
from voltage_forecasting.domain.model.aggregates.Prediction import Prediction

logger = logging.getLogger(__name__)


class NotificationServiceImpl:
    """
    Outbox of the notifications: every event stores a `pending` row per user and channel (email, push) and the
    delivery is tried right after. A delivery that fails (no SMTP, no connection, FCM down) leaves the row `pending`;
    the next dispatch sends it (US029/US030 E02). The push rows are also the inbox the app reads.
    """

    def __init__(self, repository: NotificationRepository, user_repository: UserRepository):
        self._repository = repository
        self._users = user_repository

    async def notify(self, type_code: str, users: list[User]) -> None:
        notification_type = await self._repository.find_type(type_code)
        if notification_type is None:
            raise ValueError(f"Unknown notification type: {type_code}")
        await self._repository.add_all([
            Notification(user_id=user.id, notification_type_id=notification_type.id, channel=channel)
            for user in users for channel in CHANNELS[type_code]
        ])
        await self.dispatch_pending()

    async def notify_supervisors(self, type_code: str) -> None:
        supervisors = [
            user for user in await self._users.find_all(UserStatus.ACTIVE) if user.role and user.role.name == ROLE_ADMIN
        ]
        await self.notify(type_code, supervisors)

    async def dispatch_pending(self) -> None:
        """
        Delivers every pending notification, the oldest first, emails and then pushes. One failure does not stop the rest.
        shortcut: no row lock, two dispatches at the same time can deliver the same notification twice; lock the rows if it matters.
        """
        for channel, deliver in ((NotificationChannel.EMAIL, self._send_email), (NotificationChannel.PUSH, self._send_push)):
            for notification, prediction, cell in await self._repository.find_pending(channel):
                try:
                    user = await self._users.find_by_id(notification.user_id)
                    await deliver(notification, user, prediction, cell)
                    notification.status = NotificationStatus.SENT
                    await self._repository.save(notification)
                except Exception:
                    logger.exception("Notification %s (%s) could not be sent; it stays pending", notification.id, channel.value)

    async def _send_email(self, notification: Notification, user: User, *_) -> None:
        type_code = notification.notification_type.type
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

    async def _send_push(self, notification: Notification, user: User, prediction: Prediction | None, cell: Cell | None) -> None:
        tokens = await self._repository.find_tokens(user.id)
        if not tokens:
            return  # no phone to push to: the inbox is the delivery
        body = describe(
            notification.notification_type.type,
            cell.name if cell else None,
            prediction.prediction_date if prediction else None,
            prediction.predicted_voltage if prediction else None,
        )
        invalid = await send_push(tokens, notification.notification_type.message, body, {"notification_id": str(notification.id)})
        await self._repository.delete_tokens(invalid)

    # ---- inbox and devices of the signed-in user ----

    async def mark_read(self, user_id: int, notification_id: int) -> None:
        notification = await self._repository.find_owned(user_id, notification_id)
        if notification is None:
            raise EntityNotFoundException("Notification", notification_id)
        notification.status = NotificationStatus.READ
        await self._repository.save(notification)

    async def register_device(self, user_id: int, token: str) -> DeviceToken:
        """Remembers the phone of the user; a token already known (the phone changed hands) is moved to this user."""
        device = await self._repository.find_device_by_token(token)
        if device is None:
            device = DeviceToken(user_id=user_id, token=token)
        device.user_id = user_id
        return await self._repository.save_device(device)

    async def unregister_device(self, user_id: int, device_id: int) -> None:
        device = await self._repository.find_device(user_id, device_id)
        if device is None:
            raise EntityNotFoundException("Device", device_id)
        await self._repository.delete_device(device)
