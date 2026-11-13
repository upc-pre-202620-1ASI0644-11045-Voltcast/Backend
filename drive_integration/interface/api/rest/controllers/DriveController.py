from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from iam.domain.model.aggregates.User import User
from iam.infrastructure.tokenservice.jwt.BearerTokenService import get_current_active_user, require_admin
from drive_integration.application.internal.DriveServiceImpl import DriveServiceImpl
from drive_integration.interface.api.rest.resources.DriveResource import AuthorizationUrlResponse, DriveStatusResponse
from shared.infrastructure.google.drive_client import NotConfigured
from shared.infrastructure.persistence.configuration.database_configuration import get_db_session

router = APIRouter(prefix="/api/v1/integrations/drive", tags=["Drive Integration"])

_PAGE = "<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>VoltCast</title></head><body style='font-family:sans-serif;text-align:center;margin-top:20vh'><h2>{}</h2></body></html>"
_DONE = _PAGE.format("Listo, vuelve a VoltCast")
_FAILED = _PAGE.format("No se pudo completar la conexión. Vuelve a VoltCast e inténtalo de nuevo.")  # generic on purpose: no detail leaves the server


@router.get("/connect", response_model=AuthorizationUrlResponse, summary="Google consent page to connect the company's Drive")
async def connect(user: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    """Open `authorizationUrl` in the external browser. When the supervisor accepts, Google calls the callback of the backend."""
    try:
        return {"authorizationUrl": await DriveServiceImpl(db).authorization_url(user.id)}
    except NotConfigured:
        raise HTTPException(status_code=503, detail="Drive integration is not configured")


@router.get("/callback", response_class=HTMLResponse, include_in_schema=False)
async def callback(code: str | None = Query(None), state: str | None = Query(None), db: AsyncSession = Depends(get_db_session)):
    """Called by Google, not by the app. Also called with `error` when the supervisor refuses, which ends here as a failure."""
    done = await DriveServiceImpl(db).complete(code, state)
    return HTMLResponse(_DONE if done else _FAILED, status_code=200 if done else 400)


@router.get("/status", response_model=DriveStatusResponse, summary="State of the Drive connection")
async def status(_: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db_session)):
    return await DriveServiceImpl(db).status()


@router.delete("", status_code=204, summary="Disconnect Drive and delete its tokens")
async def disconnect(_: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    await DriveServiceImpl(db).disconnect()
