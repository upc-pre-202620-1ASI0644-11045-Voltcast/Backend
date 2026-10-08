import os
from datetime import datetime, timedelta, timezone
from typing import Any
import jwt  # type: ignore[attr-defined]
from jwt.exceptions import InvalidTokenError  # type: ignore[attr-defined]
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class JWTService:
    """
    Service for JWT token generation and validation
    """

    def __init__(self):
        # Get secret from environment variable
        self.secret_key = os.getenv("JWT_SECRET_KEY")

        if not self.secret_key:
            raise ValueError(
                "JWT_SECRET_KEY not found in environment variables. "
                "Please create a .env file with JWT_SECRET_KEY or set it as an environment variable."
            )

        self.algorithm = "HS256"
        self.access_token_expire_minutes = 30  # 30 minutes
        self.refresh_token_expire_days = 7  # 7 days

    def create_access_token(self, user_id: int, email: str, role: str) -> str:
        """
        Create JWT access token
        """
        expire = datetime.now(timezone.utc) + timedelta(minutes=self.access_token_expire_minutes)

        payload = {
            "sub": str(user_id),  # Subject (user_id)
            "email": email,
            "type": "access",
            "role": role,
            "iat": datetime.now(timezone.utc),
            "exp": expire
        }

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)  # type: ignore[attr-defined]
        return token

    def create_refresh_token(self, user_id: int) -> str:
        """
        Create JWT refresh token (longer expiration)
        """
        expire = datetime.now(timezone.utc) + timedelta(days=self.refresh_token_expire_days)

        payload = {
            "sub": str(user_id),
            "type": "refresh",
            "iat": datetime.now(timezone.utc),
            "exp": expire
        }

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)  # type: ignore[attr-defined]
        return token

    def decode_token(self, token: str) -> dict[str, Any]:
        """
        Verify and decode JWT token
        Raises InvalidTokenError if token is invalid or expired
        """
        try:
            return jwt.decode(token, self.secret_key, algorithms=[self.algorithm])  # type: ignore[attr-defined]
        except InvalidTokenError as e:
            raise ValueError(f"Invalid token: {str(e)}")

    def get_user_id_from_token(self, token: str, expected_type: str = "access") -> int:
        """
        Extract user_id from token, rejecting tokens of another type (access vs refresh)
        """
        payload = self.decode_token(token)
        if payload.get("type") != expected_type:
            raise ValueError(f"Invalid token: expected a {expected_type} token")
        return int(payload["sub"])

    def get_role_from_token(self, token: str) -> str:
        payload = self.decode_token(token)
        return payload.get("role", "USER")


# Singleton instance
jwt_service = JWTService()
