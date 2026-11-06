from datetime import datetime

from pydantic import BaseModel, Field

from notification_management.domain.model.aggregates.Notification import NotificationStatus


class NotificationResponse(BaseModel):
    id: int
    type: str = Field(description="P password, R access request, A accepted, X rejected, V voltage excess, D date near")
    title: str
    body: str
    status: NotificationStatus
    created_at: datetime
    cell_id: int | None
    cell_name: str | None
    prediction_date: datetime | None

    model_config = {"from_attributes": True}


class DeviceRequest(BaseModel):
    token: str = Field(min_length=20, max_length=255, description="FCM registration token of the phone")

    model_config = {"json_schema_extra": {"examples": [{"token": "fK3x...the-token-firebase-gives-the-app"}]}}


class DeviceResponse(BaseModel):
    id: int

    model_config = {"from_attributes": True}
