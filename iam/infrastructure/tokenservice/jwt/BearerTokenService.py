from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.internal.tokenservice.JWTService import jwt_service
from iam.domain.model.aggregates.User import User
from iam.infrastructure.persistence.repositories.UserRepositoryImpl import UserRepositoryImpl
from shared.infrastructure.persistence.configuration.database_configuration import get_db_session

# Security scheme for Swagger UI
security = HTTPBearer()


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: AsyncSession = Depends(get_db_session)
) -> User:
    """
    FastAPI dependency: authenticated user from the access token.
    The account status is checked against the database on every request, so a disabled
    account loses access immediately even if its token has not expired.
    """
    try:
        user_id = jwt_service.get_user_id_from_token(credentials.credentials)
    except ValueError as e:
        raise _unauthorized(str(e))

    user = await UserRepositoryImpl(db).find_by_id(user_id)
    if not user:
        raise _unauthorized("User not found")
    if not user.can_authenticate():
        raise _unauthorized("Account is not active")
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Alias kept for the other bounded contexts: any authenticated, active user."""
    return current_user


async def require_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """Restricts an endpoint to the Supervisor role."""
    if not current_user.is_admin():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Supervisor role required")
    return current_user
