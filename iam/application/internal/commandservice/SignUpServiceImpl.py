import bcrypt

from iam.domain.model.aggregates.RegistrationRequest import RegistrationRequest
from iam.domain.model.aggregates.User import User
from iam.domain.model.commands.SignUpCommands import (
    CreateSignUpRequestCommand,
    ApproveSignUpRequestCommand,
    RejectSignUpRequestCommand,
)
from iam.domain.repositories.RegistrationRequestRepository import RegistrationRequestRepository
from iam.domain.repositories.UserRepository import UserRepository
from shared.infrastructure.email.email_client import (
    send_new_registration_request_notification,
)


class SignUpServiceImpl:

    def __init__(
        self,
        registration_repo: RegistrationRequestRepository,
        user_repo: UserRepository,
    ):
        self._registration_repo = registration_repo
        self._user_repo = user_repo

    # US024: Ingeniero crea solicitud de registro

    async def create_sign_up_request(self, command: CreateSignUpRequestCommand) -> RegistrationRequest:
        email = command.email.lower().strip()

        if await self._user_repo.exists_by_email(email):
            raise ValueError(f"Email '{email}' ya esta registrado")
        if await self._registration_repo.find_by_email(email):
            raise ValueError(f"Ya existe una solicitud pendiente para '{email}'")

        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(command.password.encode("utf-8"), salt).decode("utf-8")

        request = RegistrationRequest(
            full_name=command.full_name.strip(),
            email=email,
            password_hash=password_hash,
        )
        await self._registration_repo.create(request)

        # US027: notificar a todos los admins
        admin_emails = await self._get_admin_emails()
        for admin_email in admin_emails:
            try:
                await send_new_registration_request_notification(
                    admin_email, command.full_name.strip(), email
                )
            except Exception:
                pass  # ponytail: notificaciones no bloquean el signup

        return request

    # US020: Supervisor aprueba solicitud

    async def approve_request(self, command: ApproveSignUpRequestCommand) -> User:
        request = await self._registration_repo.find_by_id(command.request_id)
        if not request:
            raise ValueError("Solicitud no encontrada")
        if request.status.value != "pending":
            raise ValueError("Esta solicitud ya fue procesada")

        request.approve()
        await self._registration_repo.save(request)

        # Asignar rol USER por defecto
        user_role = await self._user_repo.find_role_by_name("USER")
        if not user_role:
            raise ValueError("Role USER not found in database")

        user = User(
            username=request.email.split("@")[0],
            email=request.email,
            hashed_password=request.password_hash,
            full_name=request.full_name,
            role_id=user_role.id,
            is_active=True,
        )
        return await self._user_repo.save(user)

    # US020: Supervisor rechaza solicitud

    async def reject_request(self, command: RejectSignUpRequestCommand) -> RegistrationRequest:
        request = await self._registration_repo.find_by_id(command.request_id)
        if not request:
            raise ValueError("Solicitud no encontrada")
        if request.status.value != "pending":
            raise ValueError("Esta solicitud ya fue procesada")

        request.reject()
        await self._registration_repo.save(request)
        return request

    # ── Helpers ─────────────────────────────────────────────────────────────

    async def _get_admin_emails(self) -> list[str]:
        users = await self._user_repo.find_all(role_name="ADMIN")
        return [u.email for u in users]
