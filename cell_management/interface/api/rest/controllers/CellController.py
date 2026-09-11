from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from cell_management.application.internal.commandservice.CellCommandServiceImpl import CellCommandServiceImpl
from cell_management.application.internal.queryservice.CellQueryServiceImpl import CellQueryServiceImpl
from cell_management.infrastructure.persistence.repositories.CellRepositoryImpl import CellRepositoryImpl
from cell_management.interface.api.rest.assemblers.CellResourceAssembler import CellResourceAssembler
from cell_management.interface.api.rest.resources.CellResource import CellRequest, CellUpdateRequest, CellResponse
from iam.domain.model.aggregates.User import User
from iam.infrastructure.tokenservice.jwt.BearerTokenService import get_current_active_user
from shared.infrastructure.persistence.configuration.database_configuration import get_db_session

router = APIRouter(prefix="/api/v1/cells", tags=["Cell Management"])


# =============================================================================
# READ
# =============================================================================

@router.get("", response_model=list[CellResponse], summary="List all cells")
async def list_cells(
    is_active: bool | None = Query(None, description="Filter by active status"),
    _: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        repository = CellRepositoryImpl(db)
        service = CellQueryServiceImpl(repository)
        query = CellResourceAssembler.to_get_all_query(is_active=is_active)
        cells = await service.get_all_cells(query)
        return [CellResourceAssembler.to_response(c) for c in cells]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/{cell_id}", response_model=CellResponse, summary="Get cell by ID")
async def get_cell(
    cell_id: int = Path(...),
    _: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        repository = CellRepositoryImpl(db)
        service = CellQueryServiceImpl(repository)
        query = CellResourceAssembler.to_get_by_id_query(cell_id)
        cell = await service.get_cell_by_id(query)
        if not cell:
            raise HTTPException(status_code=404, detail="Cell not found")
        return CellResourceAssembler.to_response(cell)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# =============================================================================
# CREATE
# =============================================================================

@router.post("", response_model=CellResponse, status_code=201, summary="Create new cell")
async def create_cell(
    request: CellRequest,
    _: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        repository = CellRepositoryImpl(db)
        service = CellCommandServiceImpl(repository)
        command = CellResourceAssembler.to_create_command(request)
        cell = await service.create_cell(command)
        return CellResourceAssembler.to_response(cell)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# =============================================================================
# UPDATE
# =============================================================================

@router.put("/{cell_id}", response_model=CellResponse, summary="Update cell")
async def update_cell(
    request: CellUpdateRequest,
    cell_id: int = Path(...),
    _: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        repository = CellRepositoryImpl(db)
        service = CellCommandServiceImpl(repository)
        command = CellResourceAssembler.to_update_command(cell_id, request)
        cell = await service.update_cell(command)
        return CellResourceAssembler.to_response(cell)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# =============================================================================
# DISABLE
# =============================================================================

@router.patch("/{cell_id}/disable", response_model=CellResponse, summary="Disable cell")
async def disable_cell(
    cell_id: int = Path(...),
    _: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        repository = CellRepositoryImpl(db)
        service = CellCommandServiceImpl(repository)
        command = CellResourceAssembler.to_disable_command(cell_id)
        cell = await service.disable_cell(command)
        return CellResourceAssembler.to_response(cell)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
