from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from cell_management.infrastructure.persistence.repositories.CellRepositoryImpl import CellRepositoryImpl
from iam.domain.model.aggregates.User import User
from iam.infrastructure.tokenservice.jwt.BearerTokenService import get_current_active_user, require_admin
from shared.infrastructure.persistence.configuration.database_configuration import get_db_session
from voltage_forecasting.application.internal.commandservice.AlertRuleCommandServiceImpl import AlertRuleCommandServiceImpl
from voltage_forecasting.application.internal.queryservice.TrainingQueryServiceImpl import AlertRuleQueryServiceImpl
from voltage_forecasting.infrastructure.persistence.repositories.AlertRuleRepositoryImpl import AlertRuleRepositoryImpl
from voltage_forecasting.interface.api.rest.assemblers.ForecastingResourceAssembler import ForecastingResourceAssembler
from voltage_forecasting.interface.api.rest.resources.ForecastingResource import AlertRuleRequest, AlertRuleResponse

router = APIRouter(prefix="/api/v1/alert-rules", tags=["Voltage Forecasting"])


@router.get("", response_model=list[AlertRuleResponse], summary="List the allowed voltage limits in force")
async def list_alert_rules(
    _: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        service = AlertRuleQueryServiceImpl(AlertRuleRepositoryImpl(db))
        rules = await service.get_alert_rules(ForecastingResourceAssembler.to_alert_rules_query())
        return [ForecastingResourceAssembler.to_alert_rule_response(r) for r in rules]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post("", response_model=AlertRuleResponse, status_code=201, summary="Set the maximum allowed voltage")
async def create_alert_rule(
    request: AlertRuleRequest,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Supervisor only. Without `cell_id` it is the general limit; with it, the limit of that cell."""
    try:
        service = AlertRuleCommandServiceImpl(AlertRuleRepositoryImpl(db), CellRepositoryImpl(db))
        rule = await service.create_rule(ForecastingResourceAssembler.to_create_alert_rule_command(request))
        return ForecastingResourceAssembler.to_alert_rule_response(rule)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
