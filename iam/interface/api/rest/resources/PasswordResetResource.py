from pydantic import BaseModel, EmailStr, Field


class RequestPasswordResetRequest(BaseModel):
    email: EmailStr


class ConfirmPasswordResetRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8, max_length=128)
