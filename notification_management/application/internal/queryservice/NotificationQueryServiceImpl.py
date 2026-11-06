from dataclasses import dataclass
from datetime import datetime

from notification_management.domain.model.aggregates.Notification import NotificationStatus, describe
from notification_management.domain.repositories.NotificationRepository import NotificationRepository


@dataclass
class InboxItem:
    id: int
    type: str
    title: str
    body: str
    status: NotificationStatus
    created_at: datetime
    cell_id: int | None
    cell_name: str | None
    prediction_date: datetime | None


class NotificationQueryServiceImpl:

    def __init__(self, repository: NotificationRepository):
        self._repository = repository

    async def get_inbox(self, user_id: int, status: NotificationStatus | None, limit: int) -> list[InboxItem]:
        items = []
        for notification, prediction, cell in await self._repository.find_inbox(user_id, status, limit):
            code = notification.notification_type.type
            items.append(InboxItem(
                id=notification.id,
                type=code,
                title=notification.notification_type.message,
                body=describe(
                    code,
                    cell.name if cell else None,
                    prediction.prediction_date if prediction else None,
                    prediction.predicted_voltage if prediction else None,
                ),
                status=notification.status,
                created_at=notification.created_at,
                cell_id=cell.id if cell else None,
                cell_name=cell.name if cell else None,
                prediction_date=prediction.prediction_date if prediction else None,
            ))
        return items
