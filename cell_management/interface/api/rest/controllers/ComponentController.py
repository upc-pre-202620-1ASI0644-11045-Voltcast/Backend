from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from cell_management.application.internal.commandservice.ComponentCommandServiceImpl import ComponentCommandServiceImpl
from cell_management.application.internal.queryservice.ComponentQueryServiceImpl import ComponentQueryServiceImpl
from cell_management.infrastructure.persistence.repositories.CellRepositoryImpl import CellRepositoryImpl
from cell_management.infrastructure.persistence.repositories.ComponentRepositoryImpl import ComponentRepositoryImpl
from cell_management.interface.api.rest.assemblers.ComponentResourceAssembler import ComponentResourceAssembler
from cell_management.interface.api.rest.resources.ComponentResource import (
    ComponentRequest,
    ComponentUpdateRequest,
    ComponentAssignRequest,
    ComponentSwapRequest,
    ComponentResponse,
    AssignmentHistoryResponse,
)
from iam.domain.model.aggregates.User import User
from iam.infrastructure.tokenservice.jwt.BearerTokenService import get_current_active_user
from shared.infrastructure.persistence.configuration.database_configuration import get_db_session

router = APIRouter(prefix="/api/v1/components", tags=["Component Management"])


# =============================================================================
# READ — collection routes first
# =============================================================================

@router.get("", response_model=list[ComponentResponse], summary="List all components")
async def list_components(
    component_type: str | None = Query(None, description="Filter by type (CATHODE or ANODE)"),
    cell_id: int | None = Query(None, description="Filter by assigned cell ID"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    _: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        repository = ComponentRepositoryImpl(db)
        service = ComponentQueryServiceImpl(repository)
        query = ComponentResourceAssembler.to_get_all_query(component_type=component_type, cell_id=cell_id, is_active=is_active)
        components = await service.get_all_components(query)
        return [ComponentResourceAssembler.to_response(c) for c in components]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# =============================================================================
# CREATE
# =============================================================================

@router.post("", response_model=ComponentResponse, status_code=201, summary="Create new component")
async def create_component(
    request: ComponentRequest,
    _: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        component_repo = ComponentRepositoryImpl(db)
        cell_repo = CellRepositoryImpl(db)
        service = ComponentCommandServiceImpl(component_repo, cell_repo)
        command = ComponentResourceAssembler.to_create_command(request)
        component = await service.create_component(command)
        return ComponentResourceAssembler.to_response(component)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# =============================================================================
# SWAP — before /{component_id} to avoid path conflict
# =============================================================================

@router.post("/swap", response_model=list[ComponentResponse], summary="Swap two components between cells")
async def swap_components(
    request: ComponentSwapRequest,
    _: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        component_repo = ComponentRepositoryImpl(db)
        cell_repo = CellRepositoryImpl(db)
        service = ComponentCommandServiceImpl(component_repo, cell_repo)
        command = ComponentResourceAssembler.to_swap_command(request)
        comp_a, comp_b = await service.swap_components(command)
        return [ComponentResourceAssembler.to_response(comp_a), ComponentResourceAssembler.to_response(comp_b)]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# =============================================================================
# READ — single resource
# =============================================================================

@router.get("/{component_id}", response_model=ComponentResponse, summary="Get component by ID")
async def get_component(
    component_id: int = Path(...),
    _: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        repository = ComponentRepositoryImpl(db)
        service = ComponentQueryServiceImpl(repository)
        query = ComponentResourceAssembler.to_get_by_id_query(component_id)
        component = await service.get_component_by_id(query)
        if not component:
            raise HTTPException(status_code=404, detail="Component not found")
        return ComponentResourceAssembler.to_response(component)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/{component_id}/history", response_model=list[AssignmentHistoryResponse], summary="Get component assignment history")
async def get_component_history(
    component_id: int = Path(...),
    _: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        repository = ComponentRepositoryImpl(db)
        service = ComponentQueryServiceImpl(repository)
        history = await service.get_component_history(component_id)
        return [ComponentResourceAssembler.to_history_response(h) for h in history]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# =============================================================================
# UPDATE
# =============================================================================

@router.put("/{component_id}", response_model=ComponentResponse, summary="Update component")
async def update_component(
    request: ComponentUpdateRequest,
    component_id: int = Path(...),
    _: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        component_repo = ComponentRepositoryImpl(db)
        cell_repo = CellRepositoryImpl(db)
        service = ComponentCommandServiceImpl(component_repo, cell_repo)
        command = ComponentResourceAssembler.to_update_command(component_id, request)
        component = await service.update_component(command)
        return ComponentResourceAssembler.to_response(component)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# =============================================================================
# DISABLE
# =============================================================================

@router.patch("/{component_id}/disable", response_model=ComponentResponse, summary="Disable component")
async def disable_component(
    component_id: int = Path(...),
    _: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        component_repo = ComponentRepositoryImpl(db)
        cell_repo = CellRepositoryImpl(db)
        service = ComponentCommandServiceImpl(component_repo, cell_repo)
        command = ComponentResourceAssembler.to_disable_command(component_id)
        component = await service.disable_component(command)
        return ComponentResourceAssembler.to_response(component)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# =============================================================================
# ASSIGN
# =============================================================================

@router.post("/{component_id}/assign", response_model=ComponentResponse, summary="Assign component to a cell")
async def assign_component(
    request: ComponentAssignRequest,
    component_id: int = Path(...),
    _: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        component_repo = ComponentRepositoryImpl(db)
        cell_repo = CellRepositoryImpl(db)
        service = ComponentCommandServiceImpl(component_repo, cell_repo)
        command = ComponentResourceAssembler.to_assign_command(component_id, request)
        component = await service.assign_component(command)
        return ComponentResourceAssembler.to_response(component)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
