from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from dataset_management.infrastructure.persistence.repositories.DatasetRepositoryImpl import DatasetRepositoryImpl
from iam.domain.model.aggregates.User import User
from iam.infrastructure.tokenservice.jwt.BearerTokenService import get_current_active_user
from shared.infrastructure.persistence.configuration.database_configuration import get_db_session
from shared.infrastructure.queue.task_queue import get_task_queue
from voltage_forecasting.application.internal.commandservice.TrainingCommandServiceImpl import TrainingCommandServiceImpl
from voltage_forecasting.application.internal.queryservice.TrainingQueryServiceImpl import TrainingQueryServiceImpl
from voltage_forecasting.infrastructure.persistence.repositories.TrainingRepositoryImpl import TrainingRepositoryImpl
from voltage_forecasting.interface.api.rest.assemblers.ForecastingResourceAssembler import ForecastingResourceAssembler
from voltage_forecasting.interface.api.rest.resources.ForecastingResource import TrainingRequest, TrainingResponse

router = APIRouter(prefix="/api/v1/trainings", tags=["Voltage Forecasting"])


@router.get("", response_model=list[TrainingResponse], summary="List training runs")
async def list_trainings(
    _: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        service = TrainingQueryServiceImpl(TrainingRepositoryImpl(db))
        trainings = await service.get_all_trainings(ForecastingResourceAssembler.to_all_trainings_query())
        return [ForecastingResourceAssembler.to_training_response(t) for t in trainings]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/{training_id}", response_model=TrainingResponse, summary="Get a training run")
async def get_training(
    training_id: int = Path(...),
    _: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        service = TrainingQueryServiceImpl(TrainingRepositoryImpl(db))
        training = await service.get_training_by_id(ForecastingResourceAssembler.to_training_by_id_query(training_id))
        if not training:
            raise HTTPException(status_code=404, detail="Training not found")
        return ForecastingResourceAssembler.to_training_response(training)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post("", response_model=TrainingResponse, status_code=202, summary="Train a new model version")
async def request_training(
    request: TrainingRequest,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Queues the training on a cleaned dataset. Meanwhile the latest model version keeps serving the forecasts."""
    try:
        service = TrainingCommandServiceImpl(TrainingRepositoryImpl(db), DatasetRepositoryImpl(db), get_task_queue())
        command = ForecastingResourceAssembler.to_request_training_command(request, user.id)
        return ForecastingResourceAssembler.to_training_response(await service.request_training(command))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
