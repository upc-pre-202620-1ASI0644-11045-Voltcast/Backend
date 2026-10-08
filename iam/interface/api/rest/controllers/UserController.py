from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.internal.commandservice.CommandServiceImpl import CommandServiceImpl
from iam.application.internal.queryservice.QueryServiceImpl import QueryServiceImpl
from iam.domain.model.aggregates.User import User, UserStatus
from iam.infrastructure.persistence.repositories.UserRepositoryImpl import UserRepositoryImpl
from iam.infrastructure.tokenservice.jwt.BearerTokenService import require_admin
from iam.interface.api.rest.assemblers.AuthResourceAssembler import AuthResourceAssembler
from iam.interface.api.rest.resources.AuthResponseResource import UserResponse
from iam.interface.api.rest.resources.UserRequestResource import (
    ReviewRegistrationRequest,
    UpdateUserRequest,
    ChangeUserStatusRequest,
)
from shared.domain.exceptions.domain_exceptions import EntityNotFoundException
from shared.infrastructure.persistence.configuration.database_configuration import get_db_session

# Every endpoint of this router is restricted to the Supervisor role.
router = APIRouter(prefix="/api/v1/users", tags=["User Management"])


def _handle_error(error: Exception) -> HTTPException:
    if isinstance(error, EntityNotFoundException):
        return HTTPException(status_code=404, detail=error.message)
    if isinstance(error, ValueError):
        return HTTPException(status_code=400, detail=str(error))
    return HTTPException(status_code=500, detail=f"Internal error: {str(error)}")


@router.get("", response_model=list[UserResponse], summary="List users (e.g. pending access requests)")
async def list_users(
    status: UserStatus | None = Query(None, description="Filter by account status"),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        service = QueryServiceImpl(UserRepositoryImpl(db))
        users = await service.get_all_users(AuthResourceAssembler.to_get_all_query(status))
        return [AuthResourceAssembler.to_user_response(u) for u in users]
    except Exception as e:
        raise _handle_error(e)


@router.get("/{user_id}", response_model=UserResponse, summary="Get user by ID")
async def get_user(
    user_id: int = Path(...),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        service = QueryServiceImpl(UserRepositoryImpl(db))
        user = await service.get_user_by_id(AuthResourceAssembler.to_get_by_id_query(user_id))
        if not user:
            raise EntityNotFoundException("User", user_id)
        return AuthResourceAssembler.to_user_response(user)
    except Exception as e:
        raise _handle_error(e)


@router.patch("/{user_id}/approval", response_model=UserResponse, summary="Approve or reject an access request")
async def review_registration(
    request: ReviewRegistrationRequest,
    user_id: int = Path(...),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        service = CommandServiceImpl(UserRepositoryImpl(db))
        user = await service.review_registration(AuthResourceAssembler.to_review_command(user_id, request))
        return AuthResourceAssembler.to_user_response(user)
    except Exception as e:
        raise _handle_error(e)


@router.put("/{user_id}", response_model=UserResponse, summary="Edit an engineer account")
async def update_user(
    request: UpdateUserRequest,
    user_id: int = Path(...),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        service = CommandServiceImpl(UserRepositoryImpl(db))
        user = await service.update_user(AuthResourceAssembler.to_update_user_command(user_id, request))
        return AuthResourceAssembler.to_user_response(user)
    except Exception as e:
        raise _handle_error(e)


@router.patch("/{user_id}/status", response_model=UserResponse, summary="Disable or re-enable an engineer account")
async def change_user_status(
    request: ChangeUserStatusRequest,
    user_id: int = Path(...),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        service = CommandServiceImpl(UserRepositoryImpl(db))
        user = await service.change_user_status(AuthResourceAssembler.to_change_status_command(user_id, request))
        return AuthResourceAssembler.to_user_response(user)
    except Exception as e:
        raise _handle_error(e)
