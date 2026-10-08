from datetime import datetime

from pydantic import BaseModel


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str | None
    status: str
    created_at: datetime


class AuthenticationResponse(BaseModel):
    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"


class MessageResponse(BaseModel):
    message: str
