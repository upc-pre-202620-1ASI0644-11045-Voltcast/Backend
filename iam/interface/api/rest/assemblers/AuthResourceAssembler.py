from iam.application.internal.commandservice.CommandServiceImpl import AuthenticationResponse
from iam.domain.model.aggregates.User import User, UserStatus
from iam.domain.model.commands.PasswordResetCommands import (
    RequestPasswordResetCommand,
    ConfirmPasswordResetCommand,
)
from iam.domain.model.commands.UserCommands import (
    SignInCommand,
    RegisterUserCommand,
    ReviewRegistrationCommand,
    UpdateUserCommand,
    ChangeUserStatusCommand,
)
from iam.domain.model.queries.UserQueries import GetUserByIdQuery, GetAllUsersQuery
from iam.interface.api.rest.resources.AuthRequestResource import SignInRequest, RegisterRequest
from iam.interface.api.rest.resources.AuthResponseResource import (
    UserResponse,
    AuthenticationResponse as AuthResponseDTO,
)
from iam.interface.api.rest.resources.PasswordResetResource import (
    RequestPasswordResetRequest,
    ConfirmPasswordResetRequest,
)
from iam.interface.api.rest.resources.UserRequestResource import (
    ReviewRegistrationRequest,
    UpdateUserRequest,
    ChangeUserStatusRequest,
)


class AuthResourceAssembler:

    # ── Request → Command / Query ────────────────────────────────────────────

    @staticmethod
    def to_sign_in_command(request: SignInRequest) -> SignInCommand:
        return SignInCommand(email=request.email, password=request.password)

    @staticmethod
    def to_register_command(request: RegisterRequest) -> RegisterUserCommand:
        return RegisterUserCommand(
            full_name=request.full_name,
            email=request.email,
            password=request.password,
        )

    @staticmethod
    def to_request_reset_command(request: RequestPasswordResetRequest) -> RequestPasswordResetCommand:
        return RequestPasswordResetCommand(email=request.email)

    @staticmethod
    def to_confirm_reset_command(request: ConfirmPasswordResetRequest) -> ConfirmPasswordResetCommand:
        return ConfirmPasswordResetCommand(
            email=request.email,
            code=request.code,
            new_password=request.new_password,
        )

    @staticmethod
    def to_review_command(user_id: int, request: ReviewRegistrationRequest) -> ReviewRegistrationCommand:
        return ReviewRegistrationCommand(
            user_id=user_id,
            approve=request.decision == "approve",
            role_name=request.role,
        )

    @staticmethod
    def to_update_user_command(user_id: int, request: UpdateUserRequest) -> UpdateUserCommand:
        return UpdateUserCommand(user_id=user_id, full_name=request.full_name, email=request.email)

    @staticmethod
    def to_change_status_command(user_id: int, request: ChangeUserStatusRequest) -> ChangeUserStatusCommand:
        return ChangeUserStatusCommand(user_id=user_id, enable=request.status == "active")

    @staticmethod
    def to_get_by_id_query(user_id: int) -> GetUserByIdQuery:
        return GetUserByIdQuery(user_id=user_id)

    @staticmethod
    def to_get_all_query(status: UserStatus | None = None) -> GetAllUsersQuery:
        return GetAllUsersQuery(status=status)

    # ── Domain → Response ────────────────────────────────────────────────────

    @staticmethod
    def to_user_response(user: User) -> UserResponse:
        return UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role.name if user.role else None,
            status=user.status.value,
            created_at=user.created_at,
        )

    @staticmethod
    def to_authentication_response(auth: AuthenticationResponse) -> AuthResponseDTO:
        return AuthResponseDTO(
            user=AuthResourceAssembler.to_user_response(auth.user),
            access_token=auth.access_token,
            refresh_token=auth.refresh_token,
        )
