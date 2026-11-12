from datetime import datetime

from pydantic import BaseModel


class AuthorizationUrlResponse(BaseModel):
    authorizationUrl: str


class OneDriveStatusResponse(BaseModel):
    connected: bool
    account: str | None
    lastSyncAt: datetime | None  # the last time a sync finished without error
    error: str | None  # invalid_grant (connect again) or sync_failed (it is retried at the next run)
    connectedAt: datetime | None
