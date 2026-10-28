from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from iam.domain.model.aggregates.User import User
from iam.infrastructure.tokenservice.jwt.BearerTokenService import get_current_active_user
from shared.infrastructure.persistence.configuration.database_configuration import get_db_session
from voltage_forecasting.application.internal.queryservice.ForecastQueryServiceImpl import ForecastQueryServiceImpl
from voltage_forecasting.infrastructure.persistence.repositories.AlertRuleRepositoryImpl import AlertRuleRepositoryImpl
from voltage_forecasting.infrastructure.persistence.repositories.ForecastRepositoryImpl import ForecastRepositoryImpl
from voltage_forecasting.infrastructure.persistence.repositories.TrainingRepositoryImpl import TrainingRepositoryImpl
from voltage_forecasting.interface.api.rest.assemblers.ForecastingResourceAssembler import ForecastingResourceAssembler
from voltage_forecasting.interface.api.rest.resources.ForecastingResource import ForecastResponse, MetricsResponse

router = APIRouter(prefix="/api/v1/forecasts", tags=["Voltage Forecasting"])


def _service(db: AsyncSession) -> ForecastQueryServiceImpl:
    return ForecastQueryServiceImpl(ForecastRepositoryImpl(db), TrainingRepositoryImpl(db), AlertRuleRepositoryImpl(db))


@router.get("", response_model=ForecastResponse, summary="Voltage forecasts of every cell for a date or a range")
async def list_forecasts(
    date_from: date | None = Query(None, description="First day; defaults to the first forecast day"),
    date_to: date | None = Query(None, description="Last day; defaults to date_from (a single date)"),
    cell_id: int | None = Query(None, description="Only this cell"),
    _: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Cells whose forecast exceeds the allowed voltage come with `exceeds: true`."""
    try:
        query = ForecastingResourceAssembler.to_forecasts_query(date_from, date_to, cell_id)
        return ForecastingResourceAssembler.to_forecast_response(await _service(db).get_forecasts(query))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/metrics", response_model=MetricsResponse, summary="Accuracy of the active model")
async def get_model_metrics(
    _: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        view = await _service(db).get_model_metrics(ForecastingResourceAssembler.to_metrics_query())
        return ForecastingResourceAssembler.to_metrics_response(view)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
