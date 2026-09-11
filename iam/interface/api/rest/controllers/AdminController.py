from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.internal.commandservice.CommandServiceImpl import CommandServiceImpl
from iam.application.internal.queryservice.QueryServiceImpl import QueryServiceImpl
from iam.domain.model.aggregates.User import User
from iam.domain.model.aggregates.Role import Role
from iam.infrastructure.persistence.repositories.UserRepositoryImpl import UserRepositoryImpl
from iam.infrastructure.tokenservice.jwt.BearerTokenService import get_current_active_user
from iam.interface.api.rest.assemblers.AuthResourceAssembler import AuthResourceAssembler
from iam.interface.api.rest.resources.AuthRequestResource import (
    AdminCreateUserRequest,
    AdminChangeRoleRequest,
    AdminUpdateProfileRequest,
    AdminForcePasswordResetRequest,
)
from iam.interface.api.rest.resources.AuthResponseResource import UserResponse
from shared.infrastructure.persistence.configuration.database_configuration import get_db_session

router = APIRouter(prefix="/api/v1/admin", tags=["Admin — User Management"])


# =============================================================================
# DEPENDENCY — Require admin role
# =============================================================================

async def require_admin(current_user: User = Depends(get_current_active_user)) -> User:
    if not current_user.is_admin():
        raise HTTPException(status_code=403, detail="Admin role required")
    return current_user


# =============================================================================
# READ
# =============================================================================

@router.get("/users", response_model=list[UserResponse], summary="List all users")
async def list_users(
    role: str | None = Query(None, description="Filter by role name (ADMIN or USER)"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    suspended_only: bool = Query(False, description="Show only suspended accounts"),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        repository = UserRepositoryImpl(db)
        service = QueryServiceImpl(repository)
        query = AuthResourceAssembler.to_get_all_query(
            role_name=role, is_active=is_active, suspended_only=suspended_only
        )
        users = await service.get_all_users(query)
        return [AuthResourceAssembler.to_user_response(u) for u in users]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/users/{user_id}", response_model=UserResponse, summary="Get user by ID")
async def get_user(
    user_id: int = Path(...),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        repository = UserRepositoryImpl(db)
        service = QueryServiceImpl(repository)
        query = AuthResourceAssembler.to_get_by_id_query(user_id)
        user = await service.get_user_by_id(query)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return AuthResourceAssembler.to_user_response(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# =============================================================================
# SEED — Solo funciona cuando NO hay ningun admin en la BD
# =============================================================================

class SeedAdminRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str
    password: str = Field(..., min_length=8)
    full_name: str | None = Field(None, max_length=200)

    @field_validator("email")
    @classmethod
    def email_valid(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("Invalid email format")
        return v.lower().strip()


@router.post("/seed", response_model=UserResponse, status_code=201, summary="Create first admin (only when no admins exist)")
async def seed_first_admin(
    request: SeedAdminRequest,
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(select(User).join(Role).where(Role.name == "ADMIN"))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Admin already exists — use POST /users instead")

    repository = UserRepositoryImpl(db)
    role = await repository.find_role_by_name("ADMIN")
    if not role:
        raise HTTPException(status_code=500, detail="ADMIN role not found")

    if await repository.exists_by_username(request.username.lower().strip()):
        raise HTTPException(status_code=400, detail=f"Username '{request.username}' is already taken")
    if await repository.exists_by_email(request.email.lower().strip()):
        raise HTTPException(status_code=400, detail=f"Email '{request.email}' is already registered")

    user = User(
        username=request.username.lower().strip(),
        email=request.email.lower().strip(),
        hashed_password=User.hash_password(request.password),
        full_name=request.full_name,
        role_id=role.id,
        is_active=True,
    )
    await repository.save(user)
    return AuthResourceAssembler.to_user_response(user)

@router.get(
    "/users/suspended/expired",
    response_model=list[UserResponse],
    summary="Users past 30-day grace period (ready for permanent deletion)",
)
async def get_expired_suspensions(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        repository = UserRepositoryImpl(db)
        service = QueryServiceImpl(repository)
        query = AuthResourceAssembler.to_get_suspended_past_grace_query()
        users = await service.get_suspended_past_grace(query)
        return [AuthResourceAssembler.to_user_response(u) for u in users]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# =============================================================================
# CREATE
# =============================================================================

@router.post("/users", response_model=UserResponse, status_code=201, summary="Create new user")
async def create_user(
    request: AdminCreateUserRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        repository = UserRepositoryImpl(db)
        service = CommandServiceImpl(repository)
        command = AuthResourceAssembler.to_admin_create_user_command(request, admin.id)
        user = await service.admin_create_user(command)
        return AuthResourceAssembler.to_user_response(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# =============================================================================
# ROLE
# =============================================================================

@router.patch("/users/{user_id}/role", response_model=UserResponse, summary="Change user role")
async def change_role(
    request: AdminChangeRoleRequest,
    user_id: int = Path(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        repository = UserRepositoryImpl(db)
        service = CommandServiceImpl(repository)
        command = AuthResourceAssembler.to_admin_change_role_command(user_id, request, admin.id)
        user = await service.admin_change_role(command)
        return AuthResourceAssembler.to_user_response(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# =============================================================================
# PROFILE & PASSWORD PERMISSIONS
# =============================================================================

@router.patch(
    "/users/{user_id}/grant-profile",
    response_model=UserResponse,
    summary="Grant profile edit permission",
)
async def grant_profile_edit(
    user_id: int = Path(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        repository = UserRepositoryImpl(db)
        service = CommandServiceImpl(repository)
        command = AuthResourceAssembler.to_admin_grant_profile_command(user_id, admin.id)
        user = await service.admin_grant_profile_edit(command)
        return AuthResourceAssembler.to_user_response(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.patch(
    "/users/{user_id}/revoke-profile",
    response_model=UserResponse,
    summary="Revoke profile edit permission",
)
async def revoke_profile_edit(
    user_id: int = Path(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        repository = UserRepositoryImpl(db)
        service = CommandServiceImpl(repository)
        command = AuthResourceAssembler.to_admin_revoke_profile_command(user_id, admin.id)
        user = await service.admin_revoke_profile_edit(command)
        return AuthResourceAssembler.to_user_response(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.patch(
    "/users/{user_id}/grant-password",
    response_model=UserResponse,
    summary="Grant password change permission",
)
async def grant_password_change(
    user_id: int = Path(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        repository = UserRepositoryImpl(db)
        service = CommandServiceImpl(repository)
        command = AuthResourceAssembler.to_admin_grant_password_command(user_id, admin.id)
        user = await service.admin_grant_password_change(command)
        return AuthResourceAssembler.to_user_response(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.patch(
    "/users/{user_id}/revoke-password",
    response_model=UserResponse,
    summary="Revoke password change permission",
)
async def revoke_password_change(
    user_id: int = Path(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        repository = UserRepositoryImpl(db)
        service = CommandServiceImpl(repository)
        command = AuthResourceAssembler.to_admin_revoke_password_command(user_id, admin.id)
        user = await service.admin_revoke_password_change(command)
        return AuthResourceAssembler.to_user_response(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# =============================================================================
# PROFILE & PASSWORD DIRECT EDIT (admin)
# =============================================================================

@router.put(
    "/users/{user_id}/profile",
    response_model=UserResponse,
    summary="Admin updates any user's profile directly",
)
async def admin_update_profile(
    request: AdminUpdateProfileRequest,
    user_id: int = Path(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        repository = UserRepositoryImpl(db)
        service = CommandServiceImpl(repository)
        command = AuthResourceAssembler.to_admin_update_profile_command(user_id, request, admin.id)
        user = await service.admin_update_profile(command)
        return AuthResourceAssembler.to_user_response(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.patch(
    "/users/{user_id}/reset-password",
    response_model=UserResponse,
    summary="Admin resets a user's password directly",
)
async def admin_reset_password(
    request: AdminForcePasswordResetRequest,
    user_id: int = Path(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        repository = UserRepositoryImpl(db)
        service = CommandServiceImpl(repository)
        command = AuthResourceAssembler.to_admin_force_password_reset_command(user_id, request, admin.id)
        user = await service.admin_force_password_reset(command)
        return AuthResourceAssembler.to_user_response(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# =============================================================================
# SUSPENSION LIFECYCLE
# =============================================================================

@router.patch(
    "/users/{user_id}/suspend",
    response_model=UserResponse,
    summary="Suspend user account (starts 30-day grace period)",
)
async def suspend_user(
    user_id: int = Path(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        repository = UserRepositoryImpl(db)
        service = CommandServiceImpl(repository)
        command = AuthResourceAssembler.to_admin_suspend_command(user_id, admin.id)
        user = await service.admin_suspend_user(command)
        return AuthResourceAssembler.to_user_response(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.patch(
    "/users/{user_id}/reactivate",
    response_model=UserResponse,
    summary="Reactivate suspended user (within 30-day grace period)",
)
async def reactivate_user(
    user_id: int = Path(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        repository = UserRepositoryImpl(db)
        service = CommandServiceImpl(repository)
        command = AuthResourceAssembler.to_admin_reactivate_command(user_id, admin.id)
        user = await service.admin_reactivate_user(command)
        return AuthResourceAssembler.to_user_response(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")



