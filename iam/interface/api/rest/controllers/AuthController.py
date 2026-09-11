from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.internal.commandservice.CommandServiceImpl import CommandServiceImpl
from iam.application.internal.commandservice.PasswordResetServiceImpl import PasswordResetServiceImpl
from iam.application.internal.commandservice.SignUpServiceImpl import SignUpServiceImpl
from iam.domain.model.aggregates.User import User
from iam.domain.model.commands.PasswordResetCommands import (
    RequestPasswordResetCommand,
    ConfirmPasswordResetCommand,
)
from iam.infrastructure.persistence.repositories.PasswordResetRepositoryImpl import PasswordResetRepositoryImpl
from iam.infrastructure.persistence.repositories.RegistrationRequestRepositoryImpl import RegistrationRequestRepositoryImpl
from iam.infrastructure.persistence.repositories.UserRepositoryImpl import UserRepositoryImpl
from iam.infrastructure.tokenservice.jwt.BearerTokenService import get_current_active_user
from iam.interface.api.rest.assemblers.AuthResourceAssembler import AuthResourceAssembler
from iam.interface.api.rest.assemblers.SignUpResourceAssembler import SignUpResourceAssembler
from iam.interface.api.rest.resources.AuthRequestResource import (
    SignInRequest,
    ChangePasswordRequest,
    UpdateProfileRequest,
    RefreshTokenRequest,
)
from iam.interface.api.rest.resources.AuthResponseResource import (
    UserResponse,
    AuthenticationResponse,
    TokenResponse,
)
from iam.interface.api.rest.resources.SignUpRequestResource import SignUpRequest
from iam.interface.api.rest.resources.SignUpResponseResource import SignUpResponse
from iam.interface.api.rest.resources.PasswordResetResource import (
    RequestPasswordResetRequest,
    ConfirmPasswordResetRequest,
)
from shared.infrastructure.persistence.configuration.database_configuration import get_db_session

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


# =============================================================================
# PUBLIC — No token required
# =============================================================================

@router.post("/signin", response_model=AuthenticationResponse, summary="Sign in")
async def sign_in(
    request: SignInRequest,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        repository = UserRepositoryImpl(db)
        service = CommandServiceImpl(repository)
        command = AuthResourceAssembler.to_sign_in_command(request)
        auth_response = await service.sign_in(command)
        return AuthResourceAssembler.to_authentication_response(auth_response)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post("/refresh", response_model=TokenResponse, summary="Refresh access token")
async def refresh_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        repository = UserRepositoryImpl(db)
        service = CommandServiceImpl(repository)
        access_token = await service.refresh_access_token(request.refresh_token)
        return TokenResponse(access_token=access_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post("/signup", response_model=SignUpResponse, status_code=201, summary="Request account creation")
async def sign_up(
    request: SignUpRequest,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        registration_repo = RegistrationRequestRepositoryImpl(db)
        user_repo = UserRepositoryImpl(db)
        service = SignUpServiceImpl(registration_repo, user_repo)
        command = SignUpResourceAssembler.to_create_command(request)
        result = await service.create_sign_up_request(command)
        return SignUpResourceAssembler.to_sign_up_response(result.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


class MessageResponse(BaseModel):
    message: str


@router.post(
    "/request-password-reset",
    response_model=MessageResponse,
    summary="Request password reset code",
)
async def request_password_reset(
    request: RequestPasswordResetRequest,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        reset_repo = PasswordResetRepositoryImpl(db)
        user_repo = UserRepositoryImpl(db)
        service = PasswordResetServiceImpl(reset_repo, user_repo)
        command = RequestPasswordResetCommand(email=request.email)
        await service.request_reset(command)
        return MessageResponse(message="Si el email existe, recibiras un codigo de verificacion.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post(
    "/confirm-password-reset",
    response_model=MessageResponse,
    summary="Confirm password reset with code",
)
async def confirm_password_reset(
    request: ConfirmPasswordResetRequest,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        reset_repo = PasswordResetRepositoryImpl(db)
        user_repo = UserRepositoryImpl(db)
        service = PasswordResetServiceImpl(reset_repo, user_repo)
        command = ConfirmPasswordResetCommand(
            email=request.email,
            code=request.code,
            new_password=request.new_password,
        )
        await service.confirm_reset(command)
        return MessageResponse(message="Contrasena actualizada correctamente.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# =============================================================================
# PROTECTED — Self-service (requires admin-granted permission)
# =============================================================================

@router.get("/me", response_model=UserResponse, summary="Get current user")
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    return AuthResourceAssembler.to_user_response(current_user)


@router.post(
    "/change-password",
    response_model=UserResponse,
    summary="Change own password",
    description="Requires admin to have granted `can_change_password` permission.",
)
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        repository = UserRepositoryImpl(db)
        service = CommandServiceImpl(repository)
        command = AuthResourceAssembler.to_change_password_command(current_user.id, request)
        user = await service.change_password(command)
        return AuthResourceAssembler.to_user_response(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.put(
    "/profile",
    response_model=UserResponse,
    summary="Update own profile",
    description="Requires admin to have granted `can_edit_profile` permission.",
)
async def update_profile(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        repository = UserRepositoryImpl(db)
        service = CommandServiceImpl(repository)
        command = AuthResourceAssembler.to_update_profile_command(current_user.id, request)
        user = await service.update_profile(command)
        return AuthResourceAssembler.to_user_response(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
