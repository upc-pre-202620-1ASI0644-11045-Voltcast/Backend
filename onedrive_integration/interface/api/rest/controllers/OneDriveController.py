from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from iam.domain.model.aggregates.User import User
from iam.infrastructure.tokenservice.jwt.BearerTokenService import get_current_active_user, require_admin
from onedrive_integration.application.internal.OneDriveServiceImpl import OneDriveServiceImpl
from onedrive_integration.interface.api.rest.resources.OneDriveResource import AuthorizationUrlResponse, OneDriveStatusResponse
from shared.infrastructure.microsoft.graph_client import NotConfigured
from shared.infrastructure.persistence.configuration.database_configuration import get_db_session

router = APIRouter(prefix="/api/v1/integrations/onedrive", tags=["OneDrive Integration"])

_PAGE = "<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>VoltCast</title></head><body style='font-family:sans-serif;text-align:center;margin-top:20vh'><h2>{}</h2></body></html>"
_DONE = _PAGE.format("Listo, vuelve a VoltCast")
_FAILED = _PAGE.format("No se pudo completar la conexión. Vuelve a VoltCast e inténtalo de nuevo.")  # generic on purpose: no detail leaves the server


@router.get("/connect", response_model=AuthorizationUrlResponse, summary="Microsoft consent page to connect the company's OneDrive")
async def connect(user: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    """Open `authorizationUrl` in the external browser. When the supervisor accepts, Microsoft calls the callback of the backend."""
    try:
        return {"authorizationUrl": await OneDriveServiceImpl(db).authorization_url(user.id)}
    except NotConfigured:
        raise HTTPException(status_code=503, detail="OneDrive integration is not configured")


@router.get("/callback", response_class=HTMLResponse, include_in_schema=False)
async def callback(code: str | None = Query(None), state: str | None = Query(None), db: AsyncSession = Depends(get_db_session)):
    """Called by Microsoft, not by the app. Also called with `error` when the supervisor refuses, which ends here as a failure."""
    done = await OneDriveServiceImpl(db).complete(code, state)
    return HTMLResponse(_DONE if done else _FAILED, status_code=200 if done else 400)


@router.get("/status", response_model=OneDriveStatusResponse, summary="State of the OneDrive connection")
async def status(_: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db_session)):
    return await OneDriveServiceImpl(db).status()


@router.delete("", status_code=204, summary="Disconnect OneDrive and delete its tokens")
async def disconnect(_: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    await OneDriveServiceImpl(db).disconnect()
