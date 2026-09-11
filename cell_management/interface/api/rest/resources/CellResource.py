from datetime import datetime
from pydantic import BaseModel, Field


class CellRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    voltage: float = Field(..., gt=0)

    model_config = {
        "json_schema_extra": {
            "examples": [{"name": "Celda A1", "voltage": 4.2}]
        }
    }


class CellUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    voltage: float | None = Field(None, gt=0)


class CellResponse(BaseModel):
    id: int
    name: str
    voltage: float
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
