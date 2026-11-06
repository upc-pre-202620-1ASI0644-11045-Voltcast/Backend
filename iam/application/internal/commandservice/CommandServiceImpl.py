from iam.application.internal.tokenservice.JWTService import jwt_service
from iam.domain.model.aggregates.Role import ROLE_USER
from iam.domain.model.aggregates.User import User, UserStatus
from iam.domain.model.commands.UserCommands import (
    SignInCommand,
    RegisterUserCommand,
    ReviewRegistrationCommand,
    UpdateUserCommand,
    ChangeUserStatusCommand,
)
from iam.domain.repositories.UserRepository import UserRepository
from notification_management.domain.model.aggregates.Notification import (
    ACCESS_REQUESTED,
    ACCOUNT_ACCEPTED,
    ACCOUNT_REJECTED,
)
from shared.domain.exceptions.domain_exceptions import EntityNotFoundException

INACTIVE_ACCOUNT_MESSAGES = {
    UserStatus.PENDING: "Your account request is pending approval",
    UserStatus.REJECTED: "Your account request was rejected",
    UserStatus.DISABLED: "Your account is disabled",
}


class AuthenticationResponse:
    def __init__(self, user: User, access_token: str, refresh_token: str):
        self.user = user
        self.access_token = access_token
        self.refresh_token = refresh_token


class CommandServiceImpl:
    """Command Service for the IAM context (authentication, registration requests and account management)."""

    def __init__(self, repository: UserRepository, notifier):
        self._repository = repository
        self._notifier = notifier

    # =========================================================================
    # AUTH (US021)
    # =========================================================================

    async def sign_in(self, command: SignInCommand) -> AuthenticationResponse:
        user = await self._repository.find_by_email(command.email.lower().strip())
        if not user or not user.verify_password(command.password):
            raise ValueError("Invalid credentials")
        if not user.can_authenticate():
            raise ValueError(INACTIVE_ACCOUNT_MESSAGES[user.status])

        return AuthenticationResponse(
            user=user,
            access_token=self._create_access_token(user),
            refresh_token=jwt_service.create_refresh_token(user_id=user.id),
        )

    async def refresh_access_token(self, refresh_token: str) -> str:
        try:
            user_id = jwt_service.get_user_id_from_token(refresh_token, expected_type="refresh")
        except ValueError:
            raise ValueError("Invalid or expired refresh token")

        user = await self._repository.find_by_id(user_id)
        if not user or not user.can_authenticate():
            raise ValueError("User not found or account is not active")
        return self._create_access_token(user)

    # =========================================================================
    # REGISTRATION REQUEST (US023)
    # =========================================================================

    async def register(self, command: RegisterUserCommand) -> User:
        email = command.email.lower().strip()
        hashed_password = User.hash_password(command.password)
        full_name = command.full_name.strip()

        existing = await self._repository.find_by_email(email)
        if existing and existing.status == UserStatus.REJECTED:
            # Reuse the row: user.id is a TINYINT and auto-increment values are never recycled
            existing.resubmit(full_name, hashed_password)
            user = await self._repository.save(existing)
        elif existing:
            raise ValueError(f"Email '{email}' is already registered")
        else:
            user = await self._repository.save(User(
                email=email,
                hashed_password=hashed_password,
                full_name=full_name,
                role_id=None,
                status=UserStatus.PENDING,
            ))
        await self._notifier.notify_supervisors(ACCESS_REQUESTED)  # US025
        return user

    # =========================================================================
    # SUPERVISOR — Approval (US019) and account management (US020)
    # =========================================================================

    async def review_registration(self, command: ReviewRegistrationCommand) -> User:
        user = await self._get_or_raise(command.user_id)
        if command.approve:
            role = await self._repository.find_role_by_name(command.role_name or ROLE_USER)
            if not role:
                raise ValueError(f"Role '{command.role_name}' not found")
            user.approve(role)
        else:
            user.reject()
        user = await self._repository.save(user)
        await self._notifier.notify(ACCOUNT_ACCEPTED if command.approve else ACCOUNT_REJECTED, [user])  # US029, US030
        return user

    async def update_user(self, command: UpdateUserCommand) -> User:
        user = await self._get_manageable_or_raise(command.user_id)
        email = command.email.lower().strip() if command.email else None
        if email and email != user.email and await self._repository.exists_by_email(email):
            raise ValueError(f"Email '{email}' is already registered")
        full_name = command.full_name.strip() if command.full_name else None
        user.update_profile(full_name=full_name, email=email)
        return await self._repository.save(user)

    async def change_user_status(self, command: ChangeUserStatusCommand) -> User:
        user = await self._get_manageable_or_raise(command.user_id)
        if command.enable:
            user.enable()
        else:
            user.disable()
        return await self._repository.save(user)

    # =========================================================================
    # PRIVATE
    # =========================================================================

    @staticmethod
    def _create_access_token(user: User) -> str:
        return jwt_service.create_access_token(user_id=user.id, email=user.email, role=user.role.name)

    async def _get_or_raise(self, user_id: int) -> User:
        user = await self._repository.find_by_id(user_id)
        if not user:
            raise EntityNotFoundException("User", user_id)
        return user

    async def _get_manageable_or_raise(self, user_id: int) -> User:
        """Returns an engineer account; supervisors and unreviewed requests cannot be edited or disabled."""
        user = await self._get_or_raise(user_id)
        if not user.is_engineer():
            raise ValueError("Only registered engineer accounts can be edited or disabled")
        return user
