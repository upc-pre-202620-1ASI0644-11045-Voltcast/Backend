from datetime import datetime

from pydantic import BaseModel

from dataset_management.domain.model.aggregates.UploadedDataset import DatasetStatus


class DatasetResponse(BaseModel):
    id: int
    filename: str
    upload_status: DatasetStatus
    error_message: str | None
    row_count: int
    processed_row_count: int
    created_at: datetime
    summary: dict | None = None  # only when ready: cells per section, new cells registered and covered dates

    model_config = {"from_attributes": True}
