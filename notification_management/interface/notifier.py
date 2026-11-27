from sqlalchemy.ext.asyncio import AsyncSession

from iam.infrastructure.persistence.repositories.UserRepositoryImpl import UserRepositoryImpl
from notification_management.application.internal.commandservice.NotificationServiceImpl import NotificationServiceImpl
from notification_management.infrastructure.persistence.repositories.NotificationRepositoryImpl import (
    NotificationRepositoryImpl,
)


def notifier_for(db: AsyncSession) -> NotificationServiceImpl:
    """Build the notification service bound to a database session."""
    return NotificationServiceImpl(NotificationRepositoryImpl(db), UserRepositoryImpl(db))
