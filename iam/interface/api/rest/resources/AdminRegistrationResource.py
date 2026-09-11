from pydantic import BaseModel


class ApproveResponse(BaseModel):
    message: str
    user_id: int
    username: str
    email: str


class RejectResponse(BaseModel):
    message: str
    request_id: int
    status: str
