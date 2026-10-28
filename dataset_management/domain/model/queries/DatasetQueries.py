from dataclasses import dataclass


@dataclass(frozen=True)
class GetDatasetByIdQuery:
    dataset_id: int


@dataclass(frozen=True)
class GetAllDatasetsQuery:
    pass
