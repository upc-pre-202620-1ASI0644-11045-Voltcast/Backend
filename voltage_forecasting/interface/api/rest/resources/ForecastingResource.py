from datetime import date, datetime

from pydantic import BaseModel, Field

from voltage_forecasting.domain.model.aggregates.TrainingExecution import TrainingStatus


class TrainingRequest(BaseModel):
    dataset_id: int

    model_config = {"json_schema_extra": {"examples": [{"dataset_id": 1}]}}


class TrainingResponse(BaseModel):
    id: int
    model_id: int
    dataset_id: int
    status: TrainingStatus
    rmse: float | None
    mae: float | None
    mape: float | None
    r2: float | None
    started_at: datetime
    finished_at: datetime | None
    executed_by: int | None

    model_config = {"from_attributes": True}


class AlertRuleRequest(BaseModel):
    max_voltage: float = Field(..., gt=0, description="Maximum allowed voltage (V)")
    cell_id: int | None = Field(None, description="Leave empty to set the general limit for every cell")

    model_config = {"json_schema_extra": {"examples": [{"max_voltage": 3.2, "cell_id": None}]}}


class AlertRuleResponse(BaseModel):
    id: int
    cell_id: int | None
    max_voltage: float
    is_active: bool

    model_config = {"from_attributes": True}


class ModelVersionResponse(BaseModel):
    id: int
    name: str
    version: str

    model_config = {"from_attributes": True}


class ForecastItemResponse(BaseModel):
    cell_id: int
    cell_name: str
    date: date
    voltage: float
    max_voltage: float | None
    exceeds: bool


class ForecastResponse(BaseModel):
    model: ModelVersionResponse | None
    retraining: bool
    message: str | None
    available_from: date | None
    available_to: date | None
    items: list[ForecastItemResponse]


class MetricsResponse(BaseModel):
    model: ModelVersionResponse | None
    retraining: bool
    message: str | None
    samples: int
    mse: float | None
    rmse: float | None
    mae: float | None
    mape: float | None
