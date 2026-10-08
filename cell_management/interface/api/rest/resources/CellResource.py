from pydantic import BaseModel, Field


class CellRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)

    model_config = {
        "json_schema_extra": {
            "examples": [{"name": "Celda A1"}]
        }
    }


class CellUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class CellResponse(BaseModel):
    id: int
    name: str
    barcode_value: str | None
    is_active: bool

    model_config = {"from_attributes": True}
