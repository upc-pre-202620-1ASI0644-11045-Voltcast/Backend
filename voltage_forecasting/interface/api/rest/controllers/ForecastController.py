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
from voltage_forecasting.interface.api.rest.resources.ForecastingResource import (
    EvaluationResponse,
    EvaluationSeriesResponse,
    ForecastResponse,
    MetricsResponse,
)

router = APIRouter(prefix="/api/v1/forecasts", tags=["Voltage Forecasting"])


def _service(db: AsyncSession) -> ForecastQueryServiceImpl:
    return ForecastQueryServiceImpl(ForecastRepositoryImpl(db), TrainingRepositoryImpl(db), AlertRuleRepositoryImpl(db))


@router.get("", response_model=ForecastResponse, summary="Voltage forecasts of every cell for a date or a range")
async def list_forecasts(
    date_from: date | None = Query(None, description="First day; defaults to the first forecast day"),
    date_to: date | None = Query(None, description="Last day; defaults to date_from (a single date)"),
    cell_id: int | None = Query(None, description="Only this cell"),
    exceeds: bool | None = Query(None, description="true: only the forecasts above the allowed voltage; false: only the others"),
    _: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Cells whose forecast exceeds the allowed voltage come with `exceeds: true`."""
    try:
        query = ForecastingResourceAssembler.to_forecasts_query(date_from, date_to, cell_id, exceeds)
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


@router.get("/evaluation", response_model=EvaluationResponse, summary="Forecast against measured voltage on a day of the model's backtest")
async def get_evaluation(
    day: date | None = Query(None, alias="date", description="A day of the backtest (see available_from / available_to); defaults to the latest"),
    limit: int = Query(10, ge=1, le=300, description="How many cells to return; use 300 to get all of them"),
    order: str = Query("worst", pattern="^(worst|best)$", description="worst: the cells with the largest error first; best: the smallest first"),
    _: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Compares, per cell, what the model forecast with what was measured over the last days of the data."""
    try:
        query = ForecastingResourceAssembler.to_evaluation_query(day, limit, order == "worst")
        return ForecastingResourceAssembler.to_evaluation_response(await _service(db).get_evaluation(query))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/evaluation/series", response_model=EvaluationSeriesResponse, summary="Mean forecast error of every day of the model's backtest")
async def get_evaluation_series(
    date_from: date | None = Query(None, description="First day; defaults to available_from"),
    date_to: date | None = Query(None, description="Last day; defaults to available_to"),
    _: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    """One point per day, with the same mean error that `/evaluation` reports for that day."""
    try:
        query = ForecastingResourceAssembler.to_evaluation_series_query(date_from, date_to)
        return ForecastingResourceAssembler.to_evaluation_series_response(await _service(db).get_evaluation_series(query))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
