from iam.domain.model.aggregates.RegistrationRequest import RegistrationRequest
from iam.domain.model.commands.SignUpCommands import (
    CreateSignUpRequestCommand,
    ApproveSignUpRequestCommand,
    RejectSignUpRequestCommand,
)
from iam.domain.model.queries.SignUpQueries import ListPendingSignUpRequestsQuery
from iam.domain.model.aggregates.RegistrationRequest import RegistrationStatus
from iam.interface.api.rest.resources.SignUpRequestResource import SignUpRequest
from iam.interface.api.rest.resources.SignUpResponseResource import (
    SignUpResponse,
    RegistrationRequestItem,
    RegistrationRequestList,
)


class SignUpResourceAssembler:

    @staticmethod
    def to_create_command(request: SignUpRequest) -> CreateSignUpRequestCommand:
        return CreateSignUpRequestCommand(
            full_name=request.full_name,
            email=request.email,
            password=request.password,
        )

    @staticmethod
    def to_approve_command(request_id: int) -> ApproveSignUpRequestCommand:
        return ApproveSignUpRequestCommand(request_id=request_id)

    @staticmethod
    def to_reject_command(request_id: int) -> RejectSignUpRequestCommand:
        return RejectSignUpRequestCommand(request_id=request_id)

    @staticmethod
    def to_list_query(
        status: RegistrationStatus = RegistrationStatus.PENDING,
        page: int = 1,
        page_size: int = 20,
    ) -> ListPendingSignUpRequestsQuery:
        return ListPendingSignUpRequestsQuery(status=status, page=page, page_size=page_size)

    @staticmethod
    def to_sign_up_response(request_id: int) -> SignUpResponse:
        return SignUpResponse(
            message="Solicitud de registro creada. Espera la aprobacion del supervisor.",
            request_id=request_id,
        )

    @staticmethod
    def to_request_item(r: RegistrationRequest) -> RegistrationRequestItem:
        return RegistrationRequestItem(
            id=r.id,
            full_name=r.full_name,
            email=r.email,
            status=r.status.value,
            created_at=r.created_at,
        )

    @staticmethod
    def to_request_list(
        items: list[RegistrationRequest], total: int, page: int, page_size: int
    ) -> RegistrationRequestList:
        return RegistrationRequestList(
            items=[SignUpResourceAssembler.to_request_item(r) for r in items],
            total=total,
            page=page,
            page_size=page_size,
        )
