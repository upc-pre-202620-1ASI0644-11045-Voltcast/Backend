from iam.application.internal.commandservice.CommandServiceImpl import AuthenticationResponse
from iam.domain.model.aggregates.User import User
from iam.domain.model.commands.UserCommands import (
    SignInCommand,
    ChangePasswordCommand,
    UpdateProfileCommand,
    DeactivateUserCommand,
    AdminCreateUserCommand,
    AdminChangeRoleCommand,
    AdminGrantProfileEditCommand,
    AdminRevokeProfileEditCommand,
    AdminGrantPasswordChangeCommand,
    AdminRevokePasswordChangeCommand,
    AdminSuspendUserCommand,
    AdminReactivateUserCommand,
    AdminForcePasswordResetCommand,
    AdminUpdateProfileCommand,
)
from iam.domain.model.queries.UserQueries import (
    GetUserByIdQuery,
    GetAllUsersQuery,
    GetSuspendedPastGraceQuery,
)
from iam.interface.api.rest.resources.AuthRequestResource import (
    SignInRequest,
    ChangePasswordRequest,
    UpdateProfileRequest,
    AdminCreateUserRequest,
    AdminChangeRoleRequest,
    AdminUpdateProfileRequest,
    AdminForcePasswordResetRequest,
)
from iam.interface.api.rest.resources.AuthResponseResource import (
    UserResponse,
    AuthenticationResponse as AuthResponseDTO,
)


class AuthResourceAssembler:

    # ── Request → Command ────────────────────────────────────────────────────

    @staticmethod
    def to_sign_in_command(request: SignInRequest) -> SignInCommand:
        return SignInCommand(
            username_or_email=request.username_or_email,
            password=request.password,
        )

    @staticmethod
    def to_change_password_command(user_id: int, request: ChangePasswordRequest) -> ChangePasswordCommand:
        return ChangePasswordCommand(
            user_id=user_id,
            old_password=request.old_password,
            new_password=request.new_password,
        )

    @staticmethod
    def to_update_profile_command(user_id: int, request: UpdateProfileRequest) -> UpdateProfileCommand:
        return UpdateProfileCommand(
            user_id=user_id,
            full_name=request.full_name,
            email=request.email,
        )

    @staticmethod
    def to_deactivate_command(user_id: int) -> DeactivateUserCommand:
        return DeactivateUserCommand(user_id=user_id)

    # ── Admin Request → Command ───────────────────────────────────────────────

    @staticmethod
    def to_admin_create_user_command(request: AdminCreateUserRequest, admin_id: int) -> AdminCreateUserCommand:
        return AdminCreateUserCommand(
            username=request.username,
            email=request.email,
            password=request.password,
            role_name=request.role,
            requested_by_id=admin_id,
            full_name=request.full_name,
        )

    @staticmethod
    def to_admin_change_role_command(
        target_id: int, request: AdminChangeRoleRequest, admin_id: int
    ) -> AdminChangeRoleCommand:
        return AdminChangeRoleCommand(
            target_user_id=target_id,
            new_role_name=request.role,
            requested_by_id=admin_id,
        )

    @staticmethod
    def to_admin_grant_profile_command(target_id: int, admin_id: int) -> AdminGrantProfileEditCommand:
        return AdminGrantProfileEditCommand(target_user_id=target_id, requested_by_id=admin_id)

    @staticmethod
    def to_admin_revoke_profile_command(target_id: int, admin_id: int) -> AdminRevokeProfileEditCommand:
        return AdminRevokeProfileEditCommand(target_user_id=target_id, requested_by_id=admin_id)

    @staticmethod
    def to_admin_grant_password_command(target_id: int, admin_id: int) -> AdminGrantPasswordChangeCommand:
        return AdminGrantPasswordChangeCommand(target_user_id=target_id, requested_by_id=admin_id)

    @staticmethod
    def to_admin_revoke_password_command(target_id: int, admin_id: int) -> AdminRevokePasswordChangeCommand:
        return AdminRevokePasswordChangeCommand(target_user_id=target_id, requested_by_id=admin_id)

    @staticmethod
    def to_admin_suspend_command(target_id: int, admin_id: int) -> AdminSuspendUserCommand:
        return AdminSuspendUserCommand(target_user_id=target_id, requested_by_id=admin_id)

    @staticmethod
    def to_admin_reactivate_command(target_id: int, admin_id: int) -> AdminReactivateUserCommand:
        return AdminReactivateUserCommand(target_user_id=target_id, requested_by_id=admin_id)

    @staticmethod
    def to_admin_force_password_reset_command(
        target_id: int, request: AdminForcePasswordResetRequest, admin_id: int
    ) -> AdminForcePasswordResetCommand:
        return AdminForcePasswordResetCommand(
            target_user_id=target_id,
            new_password=request.new_password,
            requested_by_id=admin_id,
        )

    @staticmethod
    def to_admin_update_profile_command(
        target_id: int, request: AdminUpdateProfileRequest, admin_id: int
    ) -> AdminUpdateProfileCommand:
        return AdminUpdateProfileCommand(
            target_user_id=target_id,
            requested_by_id=admin_id,
            full_name=request.full_name,
            email=request.email,
        )

    # ── Params → Query ───────────────────────────────────────────────────────

    @staticmethod
    def to_get_by_id_query(user_id: int) -> GetUserByIdQuery:
        return GetUserByIdQuery(user_id=user_id)

    @staticmethod
    def to_get_all_query(
        role_name: str | None = None,
        is_active: bool | None = None,
        suspended_only: bool = False,
    ) -> GetAllUsersQuery:
        return GetAllUsersQuery(role_name=role_name, is_active=is_active, suspended_only=suspended_only)

    @staticmethod
    def to_get_suspended_past_grace_query() -> GetSuspendedPastGraceQuery:
        return GetSuspendedPastGraceQuery()

    # ── Domain → Response ────────────────────────────────────────────────────

    @staticmethod
    def to_user_response(user: User) -> UserResponse:
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            role=user.role.name if user.role else "USER",
            can_edit_profile=user.can_edit_profile,
            can_change_password=user.can_change_password,
            suspended_at=user.suspended_at,
            expires_at=user.expires_at,
            days_until_deletion=user.days_until_deletion(),
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    @staticmethod
    def to_authentication_response(auth_response: AuthenticationResponse) -> AuthResponseDTO:
        return AuthResponseDTO(
            user=AuthResourceAssembler.to_user_response(auth_response.user),
            access_token=auth_response.access_token,
            refresh_token=auth_response.refresh_token,
            token_type="Bearer",
        )
