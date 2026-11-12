import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from iam.infrastructure.persistence.repositories.UserRepositoryImpl import UserRepositoryImpl
from onedrive_integration.domain.model.aggregates.OneDriveConnection import OneDriveConnection, OneDriveOAuthState
from shared.infrastructure.microsoft import graph_client as graph, token_cipher

logger = logging.getLogger(__name__)

STATE_TTL = timedelta(minutes=10)


def utcnow() -> datetime:
    """Naive UTC, as the TIMESTAMP columns keep it."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _as_utc(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=timezone.utc) if value else None


class OneDriveServiceImpl:

    def __init__(self, session: AsyncSession):
        self._session = session

    async def authorization_url(self, user_id: int) -> str:
        """The Microsoft consent page for this supervisor. Raises NotConfigured if the Azure settings are missing."""
        state = secrets.token_urlsafe(32)
        url = graph.authorization_url(state)
        await self._session.execute(delete(OneDriveOAuthState).where(OneDriveOAuthState.expires_at < utcnow()))
        self._session.add(OneDriveOAuthState(
            state_hash=hashlib.sha256(state.encode()).hexdigest(), user_id=user_id, expires_at=utcnow() + STATE_TTL
        ))
        await self._session.commit()
        return url

    async def complete(self, code: str | None, state: str | None) -> bool:
        """
        Finishes a connection the supervisor accepted at Microsoft. False for anything that goes wrong, with no detail:
        the caller shows a generic page. The state is spent before anything else, so a link cannot be used twice.
        """
        if not code or not state:
            return False
        state_hash = hashlib.sha256(state.encode()).hexdigest()
        spent = await self._session.execute(
            update(OneDriveOAuthState)
            .where(OneDriveOAuthState.state_hash == state_hash, OneDriveOAuthState.used.is_(False), OneDriveOAuthState.expires_at > utcnow())
            .values(used=True)
        )
        await self._session.commit()
        if spent.rowcount != 1:
            return False
        row = await self._session.get(OneDriveOAuthState, state_hash)
        user = await UserRepositoryImpl(self._session).find_by_id(row.user_id)
        if user is None or not user.can_authenticate() or not user.is_admin():
            return False  # the supervisor lost the role while the consent page was open
        try:
            tokens = await graph.exchange_code(code)
            account = await graph.account_email(tokens["access_token"])
            encrypted = token_cipher.encrypt(tokens["refresh_token"])
        except Exception:
            logger.exception("The OneDrive connection could not be completed")
            return False
        connection = await self._session.get(OneDriveConnection, 1) or OneDriveConnection(id=1)
        if connection.account != account:
            connection.last_sync_at = None
        connection.account, connection.refresh_token, connection.error, connection.connected_at = account, encrypted, None, utcnow()
        self._session.add(connection)
        await self._session.commit()
        return True

    async def status(self) -> dict:
        connection = await self._session.get(OneDriveConnection, 1)
        if connection is None:
            return {"connected": False, "account": None, "lastSyncAt": None, "error": None, "connectedAt": None}
        return {
            "connected": True, "account": connection.account, "lastSyncAt": _as_utc(connection.last_sync_at),
            "error": connection.error, "connectedAt": _as_utc(connection.connected_at),
        }

    async def disconnect(self) -> None:
        """Forgets the account and its token. The datasets already brought from OneDrive stay."""
        await self._session.execute(delete(OneDriveConnection))
        await self._session.commit()
