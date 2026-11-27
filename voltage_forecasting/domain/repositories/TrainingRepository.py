from typing import Protocol

from voltage_forecasting.domain.model.aggregates.MlModel import MlModel
from voltage_forecasting.domain.model.aggregates.TrainingExecution import TrainingExecution


class TrainingRepository(Protocol):

    async def create_training(self, model: MlModel, execution: TrainingExecution) -> TrainingExecution:
        """Persist a new model together with its training run."""
        ...
    async def save(self, execution: TrainingExecution) -> TrainingExecution:
        """Persist a training run and return it."""
        ...
    async def find_by_id(self, training_id: int) -> TrainingExecution | None:
        """Find a training run by its id."""
        ...
    async def find_all(self) -> list[TrainingExecution]:
        """List all training runs."""
        ...
    async def exists_running(self) -> bool:
        """Tell whether a training is running."""
        ...
