from dataset_management.domain.model.aggregates.UploadedDataset import UploadedDataset
from dataset_management.domain.model.commands.DatasetCommands import UploadDatasetCommand
from dataset_management.domain.model.queries.DatasetQueries import GetDatasetByIdQuery, GetAllDatasetsQuery
from dataset_management.interface.api.rest.resources.DatasetResource import DatasetResponse


class DatasetResourceAssembler:

    @staticmethod
    def to_upload_command(filename: str, content: bytes) -> UploadDatasetCommand:
        return UploadDatasetCommand(filename=filename, content=content)

    @staticmethod
    def to_get_by_id_query(dataset_id: int) -> GetDatasetByIdQuery:
        return GetDatasetByIdQuery(dataset_id=dataset_id)

    @staticmethod
    def to_get_all_query() -> GetAllDatasetsQuery:
        return GetAllDatasetsQuery()

    @staticmethod
    def to_response(dataset: UploadedDataset) -> DatasetResponse:
        return DatasetResponse.model_validate(dataset)
