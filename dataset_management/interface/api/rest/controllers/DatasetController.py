from fastapi import APIRouter, Depends, File, HTTPException, Path, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from dataset_management.application.internal.commandservice.DatasetCommandServiceImpl import DatasetCommandServiceImpl
from dataset_management.application.internal.queryservice.DatasetQueryServiceImpl import DatasetQueryServiceImpl
from dataset_management.infrastructure.persistence.repositories.DatasetRepositoryImpl import DatasetRepositoryImpl
from dataset_management.interface.api.rest.assemblers.DatasetResourceAssembler import DatasetResourceAssembler
from dataset_management.interface.api.rest.resources.DatasetResource import DatasetResponse
from iam.domain.model.aggregates.User import User
from iam.infrastructure.tokenservice.jwt.BearerTokenService import get_current_active_user
from shared.infrastructure.persistence.configuration.database_configuration import get_db_session
from shared.infrastructure.queue.task_queue import get_task_queue
from shared.infrastructure.storage.file_storage import get_file_storage

router = APIRouter(prefix="/api/v1/datasets", tags=["Dataset Management"])


# =============================================================================
# READ
# =============================================================================

@router.get("", response_model=list[DatasetResponse], summary="List uploaded datasets")
async def list_datasets(
    _: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        service = DatasetQueryServiceImpl(DatasetRepositoryImpl(db), get_file_storage())
        datasets = await service.get_all_datasets(DatasetResourceAssembler.to_get_all_query())
        return [DatasetResourceAssembler.to_response(d) for d in datasets]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/{dataset_id}", response_model=DatasetResponse, summary="Get the processing status of a dataset")
async def get_dataset(
    dataset_id: int = Path(...),
    _: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        service = DatasetQueryServiceImpl(DatasetRepositoryImpl(db), get_file_storage())
        dataset = await service.get_dataset_by_id(DatasetResourceAssembler.to_get_by_id_query(dataset_id))
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        return DatasetResourceAssembler.to_response(dataset, await service.get_summary(dataset))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# =============================================================================
# UPLOAD
# =============================================================================

@router.post("", response_model=DatasetResponse, status_code=201, summary="Upload a voltage history file")
async def upload_dataset(
    file: UploadFile = File(...),
    _: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Stores the Excel file and queues its cleaning; follow the progress with GET /datasets/{id}."""
    try:
        service = DatasetCommandServiceImpl(DatasetRepositoryImpl(db), get_file_storage(), get_task_queue())
        command = DatasetResourceAssembler.to_upload_command(file.filename or "", await file.read())
        dataset = await service.upload_dataset(command)
        return DatasetResourceAssembler.to_response(dataset)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
