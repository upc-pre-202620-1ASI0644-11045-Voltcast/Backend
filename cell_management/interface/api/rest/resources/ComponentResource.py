from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class ComponentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: Literal["CATHODE", "ANODE"]
    cell_id: int | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [{"name": "Catodo-01", "type": "CATHODE", "cell_id": 1}]
        }
    }


class ComponentUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    type: Literal["CATHODE", "ANODE"] | None = None


class ComponentAssignRequest(BaseModel):
    cell_id: int


class ComponentSwapRequest(BaseModel):
    component_a_id: int
    component_b_id: int


class ComponentResponse(BaseModel):
    id: int
    name: str
    type: str
    is_active: bool
    cell_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AssignmentHistoryResponse(BaseModel):
    id: int
    component_id: int
    from_cell_id: int | None
    to_cell_id: int | None
    action: str
    performed_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
