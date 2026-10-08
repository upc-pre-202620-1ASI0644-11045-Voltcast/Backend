from pydantic import BaseModel, EmailStr, Field


class SignInRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)

    model_config = {
        "json_schema_extra": {"examples": [{"email": "jperez@empresa.com", "password": "SecurePass123!"}]}
    }


class RegisterRequest(BaseModel):
    """Public endpoint: an engineer requests the creation of an account"""
    full_name: str = Field(..., min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    model_config = {
        "json_schema_extra": {
            "examples": [{"full_name": "Juan Pérez", "email": "jperez@empresa.com", "password": "SecurePass123!"}]
        }
    }


class RefreshTokenRequest(BaseModel):
    refresh_token: str
