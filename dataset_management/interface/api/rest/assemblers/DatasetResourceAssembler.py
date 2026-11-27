from dataset_management.domain.model.aggregates.UploadedDataset import UploadedDataset
from dataset_management.domain.model.commands.DatasetCommands import UploadDatasetCommand
from dataset_management.domain.model.queries.DatasetQueries import GetDatasetByIdQuery, GetAllDatasetsQuery
from dataset_management.interface.api.rest.resources.DatasetResource import DatasetResponse


class DatasetResourceAssembler:

    @staticmethod
    def to_upload_command(filename: str, content: bytes, base_dataset_id: int | None = None) -> UploadDatasetCommand:
        """Build the upload command from the received file."""
        return UploadDatasetCommand(filename=filename, content=content, base_dataset_id=base_dataset_id)

    @staticmethod
    def to_get_by_id_query(dataset_id: int) -> GetDatasetByIdQuery:
        """Build the query for one dataset."""
        return GetDatasetByIdQuery(dataset_id=dataset_id)

    @staticmethod
    def to_get_all_query() -> GetAllDatasetsQuery:
        """Build the query for all datasets."""
        return GetAllDatasetsQuery()

    @staticmethod
    def to_response(dataset: UploadedDataset, summary: dict | None = None) -> DatasetResponse:
        """Map a dataset and its optional summary to the API response."""
        return DatasetResponse.model_validate(dataset).model_copy(update={"summary": summary})
