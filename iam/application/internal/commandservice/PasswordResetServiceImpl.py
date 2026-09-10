import bcrypt

from iam.domain.model.aggregates.PasswordReset import PasswordReset
from iam.domain.model.commands.PasswordResetCommands import (
    RequestPasswordResetCommand,
    ConfirmPasswordResetCommand,
)
from iam.domain.repositories.PasswordResetRepository import PasswordResetRepository
from iam.domain.repositories.UserRepository import UserRepository
from shared.infrastructure.email.email_client import send_verification_code


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
        if not user:
            # No revelar si el email existe
            return

        # Invalidar codigos anteriores
        await self._password_reset_repo.invalidate_all_for_user(user.id)

        code = PasswordReset.generate_code()
        entry = PasswordReset(user_id=user.id, code=code)
        await self._password_reset_repo.create(entry)

        await send_verification_code(user.email, code)

    async def confirm_reset(self, command: ConfirmPasswordResetCommand) -> None:
        user = await self._user_repo.find_by_email(command.email.lower().strip())
        if not user:
            raise ValueError("Email no encontrado")

        entry = await self._password_reset_repo.find_latest_active(user.id)
        if not entry or not entry.is_valid(command.code):
            raise ValueError("Codigo invalido o expirado")

        salt = bcrypt.gensalt()
        user.hashed_password = bcrypt.hashpw(command.new_password.encode("utf-8"), salt).decode("utf-8")
        await self._user_repo.save(user)

        entry.used = True
        await self._password_reset_repo.invalidate_all_for_user(user.id)
