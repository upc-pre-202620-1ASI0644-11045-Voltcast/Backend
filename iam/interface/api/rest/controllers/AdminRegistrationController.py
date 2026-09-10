from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.internal.commandservice.SignUpServiceImpl import SignUpServiceImpl
from iam.application.internal.queryservice.SignUpQueryServiceImpl import SignUpQueryServiceImpl
from iam.domain.model.aggregates.User import User
from iam.domain.model.aggregates.RegistrationRequest import RegistrationStatus
from iam.infrastructure.persistence.repositories.RegistrationRequestRepositoryImpl import RegistrationRequestRepositoryImpl
from iam.infrastructure.persistence.repositories.UserRepositoryImpl import UserRepositoryImpl
from iam.infrastructure.tokenservice.jwt.BearerTokenService import get_current_active_user
from iam.interface.api.rest.assemblers.SignUpResourceAssembler import SignUpResourceAssembler
from iam.interface.api.rest.resources.SignUpResponseResource import RegistrationRequestList
from iam.interface.api.rest.resources.AdminRegistrationResource import ApproveResponse, RejectResponse
from shared.infrastructure.persistence.configuration.database_configuration import get_db_session

router = APIRouter(prefix="/api/v1/admin", tags=["Admin — Registration Requests"])


async def require_admin(current_user: User = Depends(get_current_active_user)) -> User:
    if not current_user.is_admin():
        raise HTTPException(status_code=403, detail="Admin role required")
    return current_user


@router.get(
    "/registration-requests",
    response_model=RegistrationRequestList,
    summary="List registration requests",
)
async def list_registration_requests(
    status: RegistrationStatus = Query(RegistrationStatus.PENDING),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        repo = RegistrationRequestRepositoryImpl(db)
        service = SignUpQueryServiceImpl(repo)
        query = SignUpResourceAssembler.to_list_query(status=status, page=page, page_size=page_size)
        requests, total = await service.list_requests(query)
        return SignUpResourceAssembler.to_request_list(requests, total, page, page_size)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.patch(
    "/registration-requests/{request_id}/approve",
    response_model=ApproveResponse,
    summary="Approve registration request",
)
async def approve_registration_request(
    request_id: int,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        registration_repo = RegistrationRequestRepositoryImpl(db)
        user_repo = UserRepositoryImpl(db)
        service = SignUpServiceImpl(registration_repo, user_repo)
        command = SignUpResourceAssembler.to_approve_command(request_id)
        user = await service.approve_request(command)
        return ApproveResponse(
            message="Solicitud aprobada. Cuenta creada.",
            user_id=user.id,
            username=user.username,
            email=user.email,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.patch(
    "/registration-requests/{request_id}/reject",
    response_model=RejectResponse,
    summary="Reject registration request",
)
async def reject_registration_request(
    request_id: int,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        registration_repo = RegistrationRequestRepositoryImpl(db)
        user_repo = UserRepositoryImpl(db)
        service = SignUpServiceImpl(registration_repo, user_repo)
        command = SignUpResourceAssembler.to_reject_command(request_id)
        result = await service.reject_request(command)
        return RejectResponse(
            message="Solicitud rechazada.",
            request_id=result.id,
            status=result.status.value,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
