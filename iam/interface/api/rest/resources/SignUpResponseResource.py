from datetime import datetime
from pydantic import BaseModel


class SignUpResponse(BaseModel):
    message: str
    request_id: int


class RegistrationRequestItem(BaseModel):
    id: int
    full_name: str
    email: str
    status: str
    created_at: datetime


class RegistrationRequestList(BaseModel):
    items: list[RegistrationRequestItem]
    total: int
    page: int
    page_size: int
