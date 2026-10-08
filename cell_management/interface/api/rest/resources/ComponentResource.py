from typing import Literal
from pydantic import BaseModel, Field

ComponentTypeName = Literal["CATHODE", "ANODE"]


class ComponentRequest(BaseModel):
    type: ComponentTypeName
    serial_code: str = Field(..., min_length=1, max_length=50)
    cell_id: int | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [{"type": "CATHODE", "serial_code": "CAT-0001", "cell_id": 1}]
        }
    }


class ComponentUpdateRequest(BaseModel):
    type: ComponentTypeName | None = None
    serial_code: str | None = Field(None, min_length=1, max_length=50)


class ComponentAssignRequest(BaseModel):
    cell_id: int


class ComponentSwapRequest(BaseModel):
    component_a_id: int
    component_b_id: int


class ComponentResponse(BaseModel):
    id: int
    type: ComponentTypeName
    serial_code: str
    is_active: bool
    cell_id: int | None

    model_config = {"from_attributes": True}
