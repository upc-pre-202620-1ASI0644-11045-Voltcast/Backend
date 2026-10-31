from dataclasses import dataclass


@dataclass(frozen=True)
class UploadDatasetCommand:
    filename: str
    content: bytes
    base_dataset_id: int | None = None
