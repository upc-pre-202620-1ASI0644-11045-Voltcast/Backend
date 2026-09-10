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
from iam.domain.repositories.UserRepository import UserRepository
from iam.application.internal.tokenservice.JWTService import jwt_service
from shared.infrastructure.email.email_client import send_password_changed_notification


class AuthenticationResponse:
    def __init__(self, user: User, access_token: str, refresh_token: str):
        self.user = user
        self.access_token = access_token
        self.refresh_token = refresh_token


class CommandServiceImpl:
    """
    Command Service for IAM Context.
    sign_up (public registration) has been removed.
    Users are created exclusively by admins via admin_create_user().
    The first admin is seeded directly in the database.
    """

    def __init__(self, repository: UserRepository):
        self._repository = repository

    # =========================================================================
    # AUTH
    # =========================================================================

    async def sign_in(self, command: SignInCommand) -> AuthenticationResponse:
        user = await self._repository.find_by_username_or_email(
            command.username_or_email.lower().strip()
        )
        if not user:
            raise ValueError("Invalid credentials")
        if not user.verify_password(command.password):
            raise ValueError("Invalid credentials")
        if not user.can_authenticate():
            raise ValueError("Account is deactivated or suspended")

        access_token = jwt_service.create_access_token(
            user_id=user.id,
            username=user.username,
            email=user.email,
            role=user.role.name if user.role else "USER",
        )
        refresh_token = jwt_service.create_refresh_token(user_id=user.id)
        return AuthenticationResponse(user, access_token, refresh_token)

    async def refresh_access_token(self, refresh_token: str) -> str:
        try:
            user_id = jwt_service.get_user_id_from_token(refresh_token)
        except ValueError:
            raise ValueError("Invalid or expired refresh token")

        user = await self._repository.find_by_id(user_id)
        if not user or not user.can_authenticate():
            raise ValueError("User not found or account deactivated")

        return jwt_service.create_access_token(
            user_id=user.id,
            username=user.username,
            email=user.email,
            role=user.role.name if user.role else "USER",
        )

    # =========================================================================
    # SELF-SERVICE (requires prior admin permission)
    # =========================================================================

    async def change_password(self, command: ChangePasswordCommand) -> User:
        user = await self._get_or_raise(command.user_id)
        user.change_password(command.old_password, command.new_password)
        result = await self._repository.save(user)
        try:
            await send_password_changed_notification(user.email, user.full_name)
        except Exception:
            pass  # ponytail: notificacion no bloquea cambio de contrasena
        return result

    async def update_profile(self, command: UpdateProfileCommand) -> User:
        user = await self._get_or_raise(command.user_id)

        if command.email and command.email != user.email:
            if await self._repository.exists_by_email(command.email):
                raise ValueError(f"Email '{command.email}' is already registered")

        user.update_profile(full_name=command.full_name, email=command.email)
        return await self._repository.save(user)

    async def deactivate_user(self, command: DeactivateUserCommand) -> User:
        """Legacy self-deactivation."""
        user = await self._get_or_raise(command.user_id)
        user.deactivate()
        return await self._repository.save(user)

    # =========================================================================
    # ADMIN — User creation
    # =========================================================================

    async def admin_create_user(self, command: AdminCreateUserCommand) -> User:
        """
        Admin creates a new user with a specific role.
        Admin users can only be created by an existing admin (safeguard).
        """
        if await self._repository.exists_by_username(command.username):
            raise ValueError(f"Username '{command.username}' is already taken")
        if await self._repository.exists_by_email(command.email):
            raise ValueError(f"Email '{command.email}' is already registered")
        if "@" not in command.email:
            raise ValueError("Invalid email format")

        # Safeguard: only an existing admin can create another admin
        if command.role_name.upper() == "ADMIN":
            caller = await self._repository.find_by_id(command.requested_by_id)
            if not caller or not caller.is_admin():
                raise ValueError("Only admins can create admin accounts")

        role = await self._repository.find_role_by_name(command.role_name)
        if not role:
            raise ValueError(f"Role '{command.role_name}' not found")

        user = User(
            username=command.username.lower().strip(),
            email=command.email.lower().strip(),
            hashed_password=User.hash_password(command.password),
            full_name=command.full_name,
            role_id=role.id,
            is_active=True,
        )
        return await self._repository.save(user)

    # =========================================================================
    # ADMIN — Role management
    # =========================================================================

    async def admin_change_role(self, command: AdminChangeRoleCommand) -> User:
        user = await self._get_or_raise(command.target_user_id)
        role = await self._repository.find_role_by_name(command.new_role_name)
        if not role:
            raise ValueError(f"Role '{command.new_role_name}' not found")
        user.role_id = role.id
        return await self._repository.save(user)

    # =========================================================================
    # ADMIN — Permission grants
    # =========================================================================

    async def admin_grant_profile_edit(self, command: AdminGrantProfileEditCommand) -> User:
        user = await self._get_or_raise(command.target_user_id)
        user.grant_profile_edit()
        return await self._repository.save(user)

    async def admin_revoke_profile_edit(self, command: AdminRevokeProfileEditCommand) -> User:
        user = await self._get_or_raise(command.target_user_id)
        user.revoke_profile_edit()
        return await self._repository.save(user)

    async def admin_grant_password_change(self, command: AdminGrantPasswordChangeCommand) -> User:
        user = await self._get_or_raise(command.target_user_id)
        user.grant_password_change()
        return await self._repository.save(user)

    async def admin_revoke_password_change(self, command: AdminRevokePasswordChangeCommand) -> User:
        user = await self._get_or_raise(command.target_user_id)
        user.revoke_password_change()
        return await self._repository.save(user)

    # =========================================================================
    # ADMIN — Account suspension lifecycle
    # =========================================================================

    async def admin_suspend_user(self, command: AdminSuspendUserCommand) -> User:
        """Suspend user — starts 30-day grace period before permanent deletion."""
        user = await self._get_or_raise(command.target_user_id)
        if user.is_admin():
            raise ValueError("Cannot suspend an admin account")
        user.suspend()
        return await self._repository.save(user)

    async def admin_reactivate_user(self, command: AdminReactivateUserCommand) -> User:
        """Cancel suspension within the 30-day grace window."""
        user = await self._get_or_raise(command.target_user_id)
        user.reactivate()
        return await self._repository.save(user)

    async def admin_force_password_reset(self, command: AdminForcePasswordResetCommand) -> User:
        """Admin sets a new password directly — no old password required."""
        user = await self._get_or_raise(command.target_user_id)
        user.force_change_password(command.new_password)
        return await self._repository.save(user)

    async def admin_update_profile(self, command: AdminUpdateProfileCommand) -> User:
        """Admin updates any user's profile directly."""
        user = await self._get_or_raise(command.target_user_id)

        if command.email and command.email != user.email:
            if await self._repository.exists_by_email(command.email):
                raise ValueError(f"Email '{command.email}' is already registered")

        user.admin_update_profile(full_name=command.full_name, email=command.email)
        return await self._repository.save(user)

    # =========================================================================
    # PRIVATE
    # =========================================================================

    async def _get_or_raise(self, user_id: int) -> User:
        user = await self._repository.find_by_id(user_id)
        if not user:
            raise ValueError(f"User not found: {user_id}")
        return user
