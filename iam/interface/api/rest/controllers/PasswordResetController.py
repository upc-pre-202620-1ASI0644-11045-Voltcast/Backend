from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.internal.commandservice.PasswordResetServiceImpl import PasswordResetServiceImpl
from iam.domain.model.commands.PasswordResetCommands import (
    RequestPasswordResetCommand,
    ConfirmPasswordResetCommand,
)
from iam.infrastructure.persistence.repositories.PasswordResetRepositoryImpl import PasswordResetRepositoryImpl
from iam.infrastructure.persistence.repositories.UserRepositoryImpl import UserRepositoryImpl
from iam.interface.api.rest.resources.PasswordResetResource import (
    RequestPasswordResetRequest,
    ConfirmPasswordResetRequest,
)
from shared.infrastructure.persistence.configuration.database_configuration import get_db_session

router = APIRouter(prefix="/api/v1/auth", tags=["Auth — Password Reset"])


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
