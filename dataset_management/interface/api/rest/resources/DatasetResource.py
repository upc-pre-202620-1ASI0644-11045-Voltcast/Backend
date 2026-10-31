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
    summary: dict | None = None  # ready: cells per section, new cells, covered dates and, except for files processed before they existed, the cleaning counts of the uploaded file alone (rows_read = rows_sorted + duplicates_removed + discarded_rows; discarded_columns); awaiting_confirmation: new and base date ranges, gap and overlap

    model_config = {"from_attributes": True}
