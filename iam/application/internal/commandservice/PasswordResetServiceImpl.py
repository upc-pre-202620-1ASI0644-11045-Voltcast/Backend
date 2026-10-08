from iam.domain.model.aggregates.PasswordReset import PasswordReset
from iam.domain.model.aggregates.User import User
from iam.domain.model.commands.PasswordResetCommands import (
    RequestPasswordResetCommand,
    ConfirmPasswordResetCommand,
)
from iam.domain.repositories.PasswordResetRepository import PasswordResetRepository
from iam.domain.repositories.UserRepository import UserRepository
from shared.infrastructure.email.email_client import send_verification_code

INVALID_CODE_MESSAGE = "Invalid or expired verification code"


class PasswordResetServiceImpl:

    def __init__(
        self,
        password_reset_repo: PasswordResetRepository,
        user_repo: UserRepository,
    ):
        self._password_reset_repo = password_reset_repo
        self._user_repo = user_repo

    async def request_reset(self, command: RequestPasswordResetCommand) -> None:
        user = await self._user_repo.find_by_email(command.email.lower().strip())
        if not user or not user.can_authenticate():
            # Do not reveal whether the email is registered
            return

        # One row per user: a new request replaces the previous code (expired or not)
        entry = await self._password_reset_repo.find_by_user(user.id)
        if entry:
            entry.renew()
        else:
            entry = PasswordReset.issue_for(user.id)
        entry = await self._password_reset_repo.save(entry)
        await send_verification_code(user.email, entry.code)

    async def confirm_reset(self, command: ConfirmPasswordResetCommand) -> None:
        user = await self._user_repo.find_by_email(command.email.lower().strip())
        if not user or not user.can_authenticate():
            raise ValueError(INVALID_CODE_MESSAGE)

        entry = await self._password_reset_repo.find_by_user(user.id)
        if not entry or not entry.is_valid(command.code):
            raise ValueError(INVALID_CODE_MESSAGE)

        User.validate_password_policy(command.new_password)
        user.reset_password(command.new_password)
        entry.mark_used()
        # Same session: one commit saves the new password and consumes the code atomically
        await self._user_repo.save(user)
