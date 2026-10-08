from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.internal.commandservice.CommandServiceImpl import CommandServiceImpl
from iam.application.internal.commandservice.PasswordResetServiceImpl import PasswordResetServiceImpl
from iam.domain.model.aggregates.User import User
from iam.infrastructure.persistence.repositories.PasswordResetRepositoryImpl import PasswordResetRepositoryImpl
from iam.infrastructure.persistence.repositories.UserRepositoryImpl import UserRepositoryImpl
from iam.infrastructure.tokenservice.jwt.BearerTokenService import get_current_active_user
from iam.interface.api.rest.assemblers.AuthResourceAssembler import AuthResourceAssembler
from iam.interface.api.rest.resources.AuthRequestResource import (
    SignInRequest,
    RegisterRequest,
    RefreshTokenRequest,
)
from iam.interface.api.rest.resources.AuthResponseResource import (
    UserResponse,
    AuthenticationResponse,
    TokenResponse,
    MessageResponse,
)
from iam.interface.api.rest.resources.PasswordResetResource import (
    RequestPasswordResetRequest,
    ConfirmPasswordResetRequest,
)
from shared.infrastructure.persistence.configuration.database_configuration import get_db_session

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


# =============================================================================
# PUBLIC — No token required
# =============================================================================

@router.post("/login", response_model=AuthenticationResponse, summary="Log in")
async def login(
    request: SignInRequest,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        service = CommandServiceImpl(UserRepositoryImpl(db))
        auth_response = await service.sign_in(AuthResourceAssembler.to_sign_in_command(request))
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
        service = CommandServiceImpl(UserRepositoryImpl(db))
        access_token = await service.refresh_access_token(request.refresh_token)
        return TokenResponse(access_token=access_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post("/register", response_model=UserResponse, status_code=201, summary="Request account creation")
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        service = CommandServiceImpl(UserRepositoryImpl(db))
        user = await service.register(AuthResourceAssembler.to_register_command(request))
        return AuthResourceAssembler.to_user_response(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post(
    "/password-reset/request",
    response_model=MessageResponse,
    summary="Request a password reset code by email",
)
async def request_password_reset(
    request: RequestPasswordResetRequest,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        service = PasswordResetServiceImpl(PasswordResetRepositoryImpl(db), UserRepositoryImpl(db))
        await service.request_reset(AuthResourceAssembler.to_request_reset_command(request))
        return MessageResponse(message="If the email is registered, a verification code has been sent.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post(
    "/password-reset/confirm",
    response_model=MessageResponse,
    summary="Confirm the verification code and set a new password",
)
async def confirm_password_reset(
    request: ConfirmPasswordResetRequest,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        service = PasswordResetServiceImpl(PasswordResetRepositoryImpl(db), UserRepositoryImpl(db))
        await service.confirm_reset(AuthResourceAssembler.to_confirm_reset_command(request))
        return MessageResponse(message="Password updated successfully.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# =============================================================================
# PROTECTED
# =============================================================================

@router.get("/me", response_model=UserResponse, summary="Get current user")
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    return AuthResourceAssembler.to_user_response(current_user)
