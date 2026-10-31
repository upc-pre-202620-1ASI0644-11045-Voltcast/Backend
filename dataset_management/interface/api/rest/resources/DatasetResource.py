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
    base_dataset_id: int | None
    created_at: datetime
    summary: dict | None = None  # ready: cells per section, new cells and covered dates; awaiting_confirmation: new and base date ranges, gap and overlap

    model_config = {"from_attributes": True}
