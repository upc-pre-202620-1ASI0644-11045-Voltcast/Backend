from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class ReviewRegistrationRequest(BaseModel):
    """Supervisor decision over a pending registration request"""
    decision: Literal["approve", "reject"]
    role: Literal["ADMIN", "USER"] = Field("USER", description="Role assigned when the request is approved")

    model_config = {"json_schema_extra": {"examples": [{"decision": "approve", "role": "USER"}]}}


class UpdateUserRequest(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=200)
    email: EmailStr | None = None


class ChangeUserStatusRequest(BaseModel):
    status: Literal["active", "disabled"]
