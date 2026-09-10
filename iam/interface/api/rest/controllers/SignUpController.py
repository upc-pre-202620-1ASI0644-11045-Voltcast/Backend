from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.internal.commandservice.SignUpServiceImpl import SignUpServiceImpl
from iam.infrastructure.persistence.repositories.RegistrationRequestRepositoryImpl import RegistrationRequestRepositoryImpl
from iam.infrastructure.persistence.repositories.UserRepositoryImpl import UserRepositoryImpl
from iam.interface.api.rest.assemblers.SignUpResourceAssembler import SignUpResourceAssembler
from iam.interface.api.rest.resources.SignUpRequestResource import SignUpRequest
from iam.interface.api.rest.resources.SignUpResponseResource import SignUpResponse
from shared.infrastructure.persistence.configuration.database_configuration import get_db_session

router = APIRouter(prefix="/api/v1/auth", tags=["Auth — Sign Up"])


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
