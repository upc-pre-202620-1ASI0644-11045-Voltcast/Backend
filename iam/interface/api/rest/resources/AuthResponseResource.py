from datetime import datetime

from pydantic import BaseModel


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: str | None
    is_active: bool
    role: str
    can_edit_profile: bool
    can_change_password: bool
    suspended_at: datetime | None
    expires_at: datetime | None
    days_until_deletion: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AuthenticationResponse(BaseModel):
    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"