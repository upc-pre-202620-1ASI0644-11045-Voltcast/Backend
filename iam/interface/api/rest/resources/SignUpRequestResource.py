from pydantic import BaseModel, Field, field_validator


class SignUpRequest(BaseModel):
    """Public endpoint: engineer requests account creation"""
    full_name: str = Field(..., min_length=2, max_length=200)
    email: str = Field(..., description="Corporate email")
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def email_valid(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("Invalid email format")
        return v.lower().strip()

    @field_validator("full_name")
    @classmethod
    def name_clean(cls, v: str) -> str:
        return v.strip()
