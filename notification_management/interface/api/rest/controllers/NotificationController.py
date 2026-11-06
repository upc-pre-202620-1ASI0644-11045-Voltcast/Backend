from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from iam.domain.model.aggregates.User import User
from iam.infrastructure.tokenservice.jwt.BearerTokenService import get_current_active_user
from notification_management.application.internal.queryservice.NotificationQueryServiceImpl import (
    NotificationQueryServiceImpl,
)
from notification_management.domain.model.aggregates.Notification import NotificationStatus
from notification_management.infrastructure.persistence.repositories.NotificationRepositoryImpl import (
    NotificationRepositoryImpl,
)
from notification_management.interface.api.rest.resources.NotificationResource import (
    DeviceRequest,
    DeviceResponse,
    NotificationResponse,
)
from notification_management.interface.notifier import notifier_for
from shared.domain.exceptions.domain_exceptions import EntityNotFoundException
from shared.infrastructure.persistence.configuration.database_configuration import get_db_session

# Every endpoint works on the notifications and phones of the signed-in user.
router = APIRouter(prefix="/api/v1/notifications", tags=["Notification Management"])


def _handle_error(error: Exception) -> HTTPException:
    if isinstance(error, EntityNotFoundException):
        return HTTPException(status_code=404, detail=error.message)
    return HTTPException(status_code=500, detail=f"Internal error: {str(error)}")


@router.get("", response_model=list[NotificationResponse], summary="My notifications, the newest first")
async def list_notifications(
    status: NotificationStatus | None = Query(None, description="pending, sent or read"),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await NotificationQueryServiceImpl(NotificationRepositoryImpl(db)).get_inbox(user.id, status, limit)
    except Exception as e:
        raise _handle_error(e)


@router.patch("/{notification_id}/read", status_code=204, summary="Mark one of my notifications as read")
async def mark_read(
    notification_id: int = Path(...),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        await notifier_for(db).mark_read(user.id, notification_id)
    except Exception as e:
        raise _handle_error(e)


@router.post("/devices", response_model=DeviceResponse, status_code=201, summary="Register my phone to receive push notifications")
async def register_device(
    request: DeviceRequest,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Call it after signing in. Keep the returned id to unregister the phone when the user signs out."""
    try:
        return await notifier_for(db).register_device(user.id, request.token)
    except Exception as e:
        raise _handle_error(e)


@router.delete("/devices/{device_id}", status_code=204, summary="Stop sending push notifications to my phone")
async def unregister_device(
    device_id: int = Path(...),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        await notifier_for(db).unregister_device(user.id, device_id)
    except Exception as e:
        raise _handle_error(e)
