from datetime import datetime, timezone

from dataset_management.domain.model.aggregates.UploadedDataset import DatasetStatus
from dataset_management.domain.repositories.DatasetRepository import DatasetRepository
from shared.infrastructure.queue.task_queue import TRAINING_QUEUE
from voltage_forecasting.domain.model.aggregates.MlModel import MlModel, MODEL_NAME
from voltage_forecasting.domain.model.aggregates.TrainingExecution import TrainingExecution
from voltage_forecasting.domain.model.commands.ForecastingCommands import RequestTrainingCommand
from voltage_forecasting.domain.repositories.TrainingRepository import TrainingRepository


class TrainingCommandServiceImpl:

    def __init__(self, repository: TrainingRepository, dataset_repository: DatasetRepository, queue):
        self._repository = repository
        self._dataset_repo = dataset_repository
        self._queue = queue

    async def request_training(self, command: RequestTrainingCommand) -> TrainingExecution:
        """
        Registers a new model version and its training run, and queues the Job that trains it, generates its
        forecasts and evaluates it. The version only becomes active when the Job finishes successfully.
        """
        dataset = await self._dataset_repo.find_by_id(command.dataset_id)
        if not dataset:
            raise ValueError(f"Dataset not found: {command.dataset_id}")
        if dataset.upload_status != DatasetStatus.READY:
            raise ValueError(f"The dataset is not ready to train (status: {dataset.upload_status.value})")
        # shortcut: check-then-insert, two simultaneous requests could both pass; fine for the few users who train.
        if await self._repository.exists_running():
            raise ValueError("A training is already in progress")

        version = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        model = MlModel(name=MODEL_NAME, version=version, artifact_path=f"models/{MODEL_NAME}/{version}")
        execution = await self._repository.create_training(
            model, TrainingExecution(dataset_id=dataset.id, executed_by=command.user_id)
        )
        try:
            await self._queue.send(TRAINING_QUEUE, {"task": "training", "training_execution_id": execution.id})
        except Exception:
            execution.mark_failed()
            await self._repository.save(execution)
            raise
        return execution
