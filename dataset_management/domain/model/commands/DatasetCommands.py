from dataclasses import dataclass


@dataclass(frozen=True)
class UploadDatasetCommand:
    filename: str
    content: bytes
    base_dataset_id: int | None = None
    auto_confirm: bool = False  # the merge is accepted without asking: the sender already checked the continuity
    extra_files: tuple[tuple[str, bytes], ...] = ()  # (filename, content) of more files of the same dataset, after `content`
